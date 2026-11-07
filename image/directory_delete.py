"""Commit deletion intent with DB changes before removing any storage objects."""
from uuid import UUID
import asyncio
from fastapi import HTTPException
from sqlalchemy import select, delete
from db import CompanyDB, ImageDB, StorageDeleteDB, ImageUploadReservationDB, StorageMoveDB
from image.directory_move import directory_prefixes


async def lock_company(session, company_id):
    company = await session.scalar(select(CompanyDB.company_id).where(
        CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True)).with_for_update())
    if company is None:
        raise HTTPException(404, 'Company not found')


async def delete_image_directory(session, body, storage):
    from image.upload_reservations import referenced
    from image.delete_guard import require_no_pending_delete
    prefix, _ = directory_prefixes(body.company_id, body.dir_path, body.dir_name, body.dir_name)
    async with session.begin():
        await lock_company(session, body.company_id)
        operation = await session.scalar(select(StorageDeleteDB).where(
            StorageDeleteDB.company_id == body.company_id, StorageDeleteDB.prefix == prefix,
            StorageDeleteDB.status == 'pending').with_for_update())
        if operation is None:
            await require_no_pending_delete(session, body.company_id)
            rows = (await session.scalars(select(ImageDB).where(ImageDB.company_id == body.company_id)
                .order_by(ImageDB.image_id).with_for_update(skip_locked=True)
                .execution_options(populate_existing=True))).all()
            expected = set((await session.scalars(select(ImageDB.image_id).where(
                ImageDB.company_id == body.company_id))).all())
            if {row.image_id for row in rows} != expected:
                raise HTTPException(409, 'Images are being edited; retry later')
            affected = [row for row in rows if (row.file_path + row.file_name).startswith(prefix)]
            for row in affected:
                if row.is_used or await referenced(session, row):
                    raise HTTPException(409, 'Directory contains images in use')
            ids = [row.image_id for row in affected]
            if ids and await session.scalar(select(ImageUploadReservationDB.image_id).where(
                    ImageUploadReservationDB.company_id == body.company_id,
                    ImageUploadReservationDB.image_id.in_(ids)).limit(1)):
                raise HTTPException(409, 'Directory contains unverified uploads')
            if await session.scalar(select(StorageMoveDB.operation_id).where(
                    StorageMoveDB.company_id == body.company_id, StorageMoveDB.status == 'pending').limit(1)):
                raise HTTPException(409, 'Storage move pending; resolve it before deletion')
            try:
                async with asyncio.timeout(30):
                    listed = await storage.get_objects_by_dir_name(dir_name=prefix)
            except TimeoutError:
                raise HTTPException(503, 'Storage temporarily unavailable') from None
            keys = sorted(set(listed) | {row.file_path + row.file_name for row in affected})
            if any(not key.startswith(prefix) or '\\' in key or any(p in ('.', '..') for p in key.split('/')) for key in keys):
                raise HTTPException(503, 'Invalid storage listing')
            operation = StorageDeleteDB(company_id=body.company_id, prefix=prefix,
                keys=keys, image_ids=[str(key) for key in ids], status='pending')
            session.add(operation)
            if ids:
                await session.execute(delete(ImageDB).where(ImageDB.company_id == body.company_id,
                                                            ImageDB.image_id.in_(ids)))
            await session.flush()
        operation_id = operation.operation_id
        image_ids = [UUID(value) for value in operation.image_ids]
    await retry_directory_delete(session, body.company_id, operation_id, storage)
    return image_ids


async def retry_directory_delete(session, company_id, operation_id, storage):
    # The intent is durable before the first destructive request.
    async with session.begin():
        await lock_company(session, company_id)
        operation = await session.scalar(select(StorageDeleteDB).where(
            StorageDeleteDB.company_id == company_id, StorageDeleteDB.operation_id == operation_id)
            .with_for_update().execution_options(populate_existing=True))
        if operation is None:
            raise HTTPException(404, 'Deletion operation not found')
        if operation.status == 'pending':
            try:
                async with asyncio.timeout(30):
                    await storage.delete_recorded_keys(operation.keys, company_id)
            except TimeoutError:
                raise HTTPException(503, 'Deletion remains pending; retry required') from None
            operation.status = 'done'
    return {'operation_id': operation_id, 'status': 'done'}
