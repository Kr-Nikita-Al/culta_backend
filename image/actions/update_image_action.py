from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from db import ImageDB, CompanyDB
from image.move_journal import MoveJournal

from image.model_dal import ImageDal


def get_storage():
    # Router packages import image.actions during application bootstrap.
    from s3_directory.storage import S3Client
    return S3Client()


async def __update_image_by_id(update_image_params: Dict, image_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    journal = None
    async with session.begin():
        company_id = await session.scalar(select(ImageDB.company_id).where(ImageDB.image_id == image_id))
        if company_id is None:
            return None
        # Same lock order as creation, directory moves and cleanup: company, image.
        company = await session.scalar(select(CompanyDB.company_id).where(
            CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True)).with_for_update())
        if company is None:
            raise HTTPException(404, 'Company not found')
        from image.delete_guard import require_no_pending_delete
        await require_no_pending_delete(session, company_id)
        current = await session.scalar(select(ImageDB).where(ImageDB.image_id == image_id,
                                       ImageDB.company_id == company_id)
                                       .with_for_update().execution_options(populate_existing=True))
        if current is None:
            return None
        if current.is_used:
            raise HTTPException(409, 'Image is in use')
        # Storage names are identifiers, not display titles. Changing only the
        # database name would leave the image pointing at a nonexistent object.
        if update_image_params.get('file_name', current.file_name) != current.file_name:
            raise HTTPException(422, 'Use title to rename the image')
        old_path, name, company_id = current.file_path, current.file_name, current.company_id
        new_path = update_image_params.get('file_path', old_path)
        if new_path != old_path:
            occupied = await session.scalar(select(ImageDB.image_id).where(
                ImageDB.company_id == company_id, ImageDB.file_path + ImageDB.file_name == new_path + name,
                ImageDB.image_id != image_id).limit(1))
            if occupied is not None:
                raise HTTPException(409, 'Destination image already exists')
        image = ImageDal(session)
        updated_image_id = await image.update_image(
            image_id=image_id,
            **update_image_params
        )
        # Validate/flush database changes before touching storage. Commit follows
        # the copy; the source is retained even if commit fails afterwards.
        await session.flush()
        if updated_image_id is not None and new_path != old_path:
            journal = MoveJournal(session, company_id=company_id, image_id=image_id, kind='image',
                source_key=old_path + name, destination_key=new_path + name)
            copied_keys = await get_storage().update_file_place_object(old_file_path=old_path,
                new_file_path=new_path, file_name=name, company_id=company_id, before_copy=journal.prepare)
            await journal.finish(copied_keys)
    if journal is not None:
        from image.move_cleanup import try_cleanup_move
        await try_cleanup_move(session, company_id, journal.operation_id)
    return updated_image_id
