"""Conservative lazy cleanup; caller holds the company's quota lock.

Never deletes storage objects. A day's grace follows the two-minute upload URL
expiry, allowing interrupted/in-flight uploads to finish before checking HEAD.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from botocore.exceptions import BotoCoreError
from sqlalchemy import select, or_
from db import ImageDB, ImageUploadReservationDB, CompanyDB, ProductCardDB, UserRoleDB
from s3_directory.storage import S3Client
from utils.constants import IMAGE_UPLOAD_URL_TTL_SECONDS

logger = logging.getLogger(__name__)
UPLOAD_CLEANUP_GRACE = timedelta(days=1)


def track_upload(session, image):
    session.add(ImageUploadReservationDB(image_id=image.image_id, company_id=image.company_id,
        object_key=image.file_path + image.file_name,
        cleanup_after=datetime.now(timezone.utc) + timedelta(seconds=IMAGE_UPLOAD_URL_TTL_SECONDS)
        + UPLOAD_CLEANUP_GRACE))


async def referenced(session, image):
    for model, condition in (
        (CompanyDB, or_(CompanyDB.image_picture_id == image.image_id, CompanyDB.image_icon_id == image.image_id)),
        (ProductCardDB, or_(ProductCardDB.image_product_id == image.image_id, ProductCardDB.image_icon_id == image.image_id)),
        (UserRoleDB, UserRoleDB.avatar_id == image.image_id),
    ):
        if await session.scalar(select(select(model).where(condition).exists())):
            return True
    return False


async def cleanup_expired_uploads(session, company_id):
    # Lock images too: reference assignment takes a share lock on these rows.
    # SKIP LOCKED avoids waiting for another editor while holding the company lock.
    rows = (await session.execute(select(ImageUploadReservationDB, ImageDB).join(ImageDB,
        (ImageDB.image_id == ImageUploadReservationDB.image_id)
        & (ImageDB.company_id == ImageUploadReservationDB.company_id)).where(
            ImageUploadReservationDB.company_id == company_id,
            ImageUploadReservationDB.cleanup_after <= datetime.now(timezone.utc))
        .order_by(ImageUploadReservationDB.cleanup_after).limit(50)
        .with_for_update(skip_locked=True))).all()
    if not rows:
        return
    storage = S3Client()
    missing_images = []
    # Bound storage latency for this request. Unchecked reservations remain intact.
    deadline = asyncio.get_running_loop().time() + 5
    for reservation, image in rows:
        if image.is_used or image.file_path + image.file_name != reservation.object_key or await referenced(session, image):
            await session.delete(reservation)  # Retain the image and its quota permanently.
            continue
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            break
        try:
            metadata = await asyncio.wait_for(storage.get_object_metadata(reservation.object_key),
                                              timeout=min(2, remaining))
        except (HTTPException, TimeoutError, BotoCoreError):
            logger.warning('Upload reservation retained: storage verification unavailable')
            break
        if metadata == {}:
            # Only a confirmed missing object is eligible; no S3 delete is performed.
            missing_images.append(image)
        await session.delete(reservation)
    # Delete markers first: the FK also cascades on image deletion, and ORM
    # flush ordering without a relationship must not double-delete the marker.
    await session.flush()
    for image in missing_images:
        await session.delete(image)
    await session.flush()
