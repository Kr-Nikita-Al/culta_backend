"""Company row lock serializes quota checks and image reservations."""
import math

from fastapi import HTTPException
from sqlalchemy import select, func
from db import CompanyDB, ImageDB
from utils.constants import QUOTA_COUNT_IMAGES_BY_COMPANY, QUOTA_IMAGE_SIZE, QUOTA_STORAGE_SIZE


async def reserve_image_quota(session, company_id, size):
    if not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0 or size != int(size) or size > QUOTA_IMAGE_SIZE:
        raise HTTPException(422, 'Incorrect file size')
    company = await session.scalar(select(CompanyDB.company_id).where(
        CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True)).with_for_update())
    if company is None:
        raise HTTPException(404, 'Company not found')
    from image.delete_guard import require_no_pending_delete
    await require_no_pending_delete(session, company_id)
    from image.upload_reservations import cleanup_expired_uploads
    await cleanup_expired_uploads(session, company_id)
    count, used = (await session.execute(select(func.count(ImageDB.image_id),
        func.coalesce(func.sum(ImageDB.size), 0)).where(ImageDB.company_id == company_id))).one()
    # Include pending uploads: issuing an upload URL reserves both count and bytes.
    if count >= QUOTA_COUNT_IMAGES_BY_COMPANY:
        raise HTTPException(422, 'Image count quota exceeded')
    if not math.isfinite(used) or used < 0 or used + size > QUOTA_STORAGE_SIZE:
        raise HTTPException(422, 'Storage size quota exceeded')
