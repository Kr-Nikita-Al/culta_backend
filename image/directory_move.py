"""Update a directory's image paths atomically, preserving nested paths."""
from fastapi import HTTPException
from sqlalchemy import select
from db import CompanyDB, ImageDB
from image.move_journal import MoveJournal


def directory_prefixes(company_id, parent, old_name, new_name):
    root = f'company_images/company_{company_id}/'
    if (not parent.startswith(root) or not parent.endswith('/')
            or any(part in ('.', '..') for part in parent.split('/'))):
        raise HTTPException(422, 'Incorrect directory path')
    for name in (old_name, new_name):
        if (not name.endswith('/') or not name[:-1] or '/' in name[:-1]
                or '\\' in name or name[:-1] in ('.', '..')):
            raise HTTPException(422, 'Incorrect directory name')
    return parent + old_name, parent + new_name


async def rename_image_directory(session, body, storage):
    old, new = directory_prefixes(body.company_id, body.dir_path, body.old_dir_name, body.new_dir_name)
    async with session.begin():
        company = await session.scalar(select(CompanyDB.company_id).where(
            CompanyDB.company_id == body.company_id, CompanyDB.is_active.is_(True)).with_for_update())
        if company is None:
            raise HTTPException(404, 'Company not found')
        from image.delete_guard import require_no_pending_delete
        await require_no_pending_delete(session, body.company_id)
        images = (await session.scalars(select(ImageDB).where(ImageDB.company_id == body.company_id)
            .order_by(ImageDB.image_id).with_for_update().execution_options(populate_existing=True))).all()
        affected = [image for image in images if image.file_path.startswith(old)]
        if old == new:
            return [image.image_id for image in affected]
        if any(image.file_path.startswith(new) for image in images):
            raise HTTPException(409, 'Destination directory already exists')
        for image in affected:
            image.file_path = new + image.file_path[len(old):]
        await session.flush()
        # Copy all files once. Originals remain available if commit fails.
        journal = MoveJournal(session, company_id=body.company_id, kind='directory',
                              source_key=old, destination_key=new)
        copied_keys = await storage.rename_directory(body.dir_path, body.old_dir_name, body.new_dir_name,
                                       body.company_id, before_copy=journal.prepare)
        await journal.finish(copied_keys)
        result = [image.image_id for image in affected]
    from image.move_cleanup import try_cleanup_move
    await try_cleanup_move(session, body.company_id, journal.operation_id)
    return result
