"""Persist intent independently; confirm it with the image-path transaction."""
from uuid import uuid4
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from db import StorageMoveDB


class MoveJournal:
    def __init__(self, session, **metadata):
        self.session = session
        self.metadata = metadata
        self.operation_id = None

    async def prepare(self, keys):
        if self.operation_id is not None:
            raise RuntimeError('Copy intent already recorded')
        operation_id = uuid4()
        # No FK to a locked image/company: this commit must survive outer rollback.
        # If it fails (even with an ambiguous outcome), copying MUST NOT start.
        async with AsyncSession(bind=self.session.bind) as journal, journal.begin():
            journal.add(StorageMoveDB(operation_id=operation_id, status='pending',
                copied_keys=keys, **self.metadata))
        self.operation_id = operation_id

    async def finish(self, copied_keys=None):
        if self.operation_id is None:
            raise RuntimeError('Storage copy was not journaled')
        values = {'status':'committed'}
        if copied_keys is not None:
            values['copied_keys'] = copied_keys
        await self.session.execute(update(StorageMoveDB).where(
            StorageMoveDB.operation_id == self.operation_id).values(**values))
