"""Validate tenant-scoped references inside the caller's write transaction."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from db import ImageDB, ScreenDB
from utils.constants import EMPTY_UUID


async def validate_company_references(session, company_id, values, *, image_fields=(), screen_fields=()):
    for fields, model, key in ((image_fields, ImageDB, ImageDB.image_id),
                               (screen_fields, ScreenDB, ScreenDB.screen_id)):
        for field in fields:
            if field not in values:
                continue
            try:
                value = UUID(str(values[field]))
            except (ValueError, TypeError, AttributeError):
                raise HTTPException(422, f'{field}: expected UUID') from None
            if value == EMPTY_UUID:
                continue  # Existing API convention: detach the optional link.
            # Share lock prevents deletion/ownership changes before this write commits.
            result = await session.execute(select(key).where(key == value,
                model.company_id == company_id).with_for_update(read=True))
            if result.scalar_one_or_none() is None:
                # Do not reveal whether another tenant owns the supplied identifier.
                raise HTTPException(422, f'{field}: object not found in this company')
