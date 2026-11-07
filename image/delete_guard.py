"""Caller holds the company lock; serialize new storage writes with deletion."""
from fastapi import HTTPException
from sqlalchemy import select
from db import StorageDeleteDB


async def require_no_pending_delete(session, company_id):
    operation = await session.scalar(select(StorageDeleteDB.operation_id).where(
        StorageDeleteDB.company_id == company_id, StorageDeleteDB.status == 'pending').limit(1))
    if operation is not None:
        raise HTTPException(409, 'Directory deletion pending; retry deleting that directory first')
