import asyncio
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from sqlalchemy.orm import Session
from db import StorageMoveDB, ImageDB
from image.move_cleanup import cleanup_move

pytestmark = pytest.mark.integration


def seed(pg, mode='ok'):
    root = f"company_images/company_{pg.ids['company_a']}/"
    pair = {'source':root+'old/a.png', 'destination':root+'new/a.png',
            'source_version':'old-v1', 'destination_version':'copy-v2'}
    if mode == 'legacy': pair.pop('source_version')
    if mode == 'null': pair['source_version'] = 'null'
    if mode == 'foreign': pair['source'] = f"company_images/company_{pg.ids['company_b']}/a.png"
    operation = uuid4()
    with Session(pg.engine) as session, session.begin():
        session.add(StorageMoveDB(operation_id=operation, company_id=pg.ids['company_a'], kind='image',
            source_key=pair['source'], destination_key=pair['destination'], copied_keys=[pair],
            status='pending' if mode == 'pending' else 'committed'))
        session.add(ImageDB(image_id=uuid4(), company_id=pg.ids['company_a'],
            file_path=root+('old/' if mode == 'referenced' else 'new/'), file_name='a.png'))
        if mode == 'protected':
            session.add(StorageMoveDB(company_id=pg.ids['company_a'], kind='image', source_key=pair['source'],
                destination_key=root+'another/a.png', copied_keys=[pair], status='pending'))
    versions = {(pair['source'],'old-v1'), (pair['source'],'newer-v3'), (pair['destination'],'copy-v2')}
    if mode == 'missing_target': versions.discard((pair['destination'],'copy-v2'))
    async def head(key, version):
        if mode == 'error': raise HTTPException(503, 'Unavailable')
        return {'version_id':version} if (key,version) in versions else None
    async def delete(key, version, company): versions.discard((key,version))
    storage = SimpleNamespace(versioning_enabled=AsyncMock(return_value=mode != 'disabled'),
        get_version_metadata=AsyncMock(side_effect=head), delete_exact_version=AsyncMock(side_effect=delete))
    return operation, pair, storage, versions


def test_deletes_only_old_version_and_retry_is_idempotent(pg):
    operation, pair, storage, versions = seed(pg)
    async def scenario():
        async with pg.sessions() as session:
            result = await cleanup_move(session, pg.ids['company_a'], operation, storage)
            assert result['deleted'] == 1
            result = await cleanup_move(session, pg.ids['company_a'], operation, storage)
            assert result['deleted'] == 0
    asyncio.run(scenario())
    storage.delete_exact_version.assert_awaited_once_with(pair['source'], 'old-v1', pg.ids['company_a'])
    assert (pair['source'],'newer-v3') in versions
    assert (pair['destination'],'copy-v2') in versions


@pytest.mark.parametrize('mode', ['legacy', 'null', 'foreign', 'pending', 'protected', 'referenced', 'missing_target', 'disabled', 'error'])
def test_unsafe_or_unverifiable_sources_are_kept(pg, mode):
    operation, pair, storage, versions = seed(pg, mode)
    async def scenario():
        async with pg.sessions() as session:
            await cleanup_move(session, pg.ids['company_a'], operation, storage)
    asyncio.run(scenario())
    storage.delete_exact_version.assert_not_awaited()
    assert (pair['source'],'old-v1') in versions


def test_cleanup_rechecks_after_database_commit_failure(pg):
    operation, pair, storage, versions = seed(pg)
    async def scenario():
        async with pg.sessions() as session:
            def fail(_): raise RuntimeError('Commit failed')
            event.listen(session.sync_session, 'before_commit', fail)
            with pytest.raises(RuntimeError):
                await cleanup_move(session, pg.ids['company_a'], operation, storage)
        async with pg.sessions() as session:
            result = await cleanup_move(session, pg.ids['company_a'], operation, storage)
            assert result['already_absent'] == 1
    asyncio.run(scenario())
    assert storage.delete_exact_version.await_count == 1


def test_locked_images_and_other_companies_are_not_cleaned(pg):
    operation, _, storage, _ = seed(pg)
    async def scenario():
        async with pg.sessions() as editor, editor.begin():
            await editor.execute(select(ImageDB.image_id).with_for_update())
            async with pg.sessions() as session:
                result = await cleanup_move(session, pg.ids['company_a'], operation, storage)
                assert result['busy'] is True
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await cleanup_move(session, pg.ids['company_b'], operation, storage)
            assert error.value.status_code == 404
    asyncio.run(scenario())
    storage.delete_exact_version.assert_not_awaited()
