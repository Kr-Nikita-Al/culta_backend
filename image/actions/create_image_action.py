from uuid import UUID
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from db import ImageDB

from image.interface_request import CreateImageRequest
from image.interface_response import CreateImageInterface
from image.model_dal import ImageDal
from image.quotas import reserve_image_quota


async def __create_image(image_body: CreateImageRequest, user_id: UUID, session: AsyncSession,
                         before_commit: Optional[Callable[[], Awaitable[None]]] = None,
                         pending_upload: bool = False) -> CreateImageInterface:
    async with session.begin():
        await reserve_image_quota(session, image_body.company_id, image_body.size)
        # The company quota lock also serializes ownership of storage keys.
        # Compare the actual key, not its potentially different path/name split.
        occupied = await session.scalar(select(ImageDB.image_id).where(
            ImageDB.company_id == image_body.company_id,
            ImageDB.file_path + ImageDB.file_name == image_body.file_path + image_body.file_name).limit(1))
        if occupied is not None:
            raise HTTPException(409, 'Image storage key is already reserved')
        image_dal = ImageDal(session)
        image_db = await image_dal.create_image(
            image_body.__dict__, creator_user_id=user_id
        )
        if pending_upload:
            from image.upload_reservations import track_upload
            track_upload(session, image_db)
        result = CreateImageInterface(
            image_id=image_db.image_id,
            company_id=image_db.company_id,
            company_group_id=image_db.company_group_id,
            title=image_db.title,
            file_name=image_db.file_name,
            type_col=image_db.type_col,
            image_type=image_db.image_type,
            file_path=image_db.file_path,
            resolution=image_db.resolution,
            tags=image_db.tags,
            order_number=image_db.order_number,
            size=image_db.size,
            width=image_db.width,
            height=image_db.height,
            is_hidden=image_db.is_hidden,
            is_used=image_db.is_used,
            creator_id=image_db.creator_id,
            time_created=image_db.time_created
        )
        # A failed storage upload must roll back the newly flushed database row.
        if before_commit is not None:
            await before_commit()
        return result
