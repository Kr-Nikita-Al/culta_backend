import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, event
from db import ImageDB, StorageDeleteDB
from image.actions.create_image_action import __create_image
from image.directory_delete import delete_image_directory, retry_directory_delete
from image.actions.update_image_action import __update_image_by_id
from image.directory_move import rename_image_directory
from tests.integration.test_image_quotas import body

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('failure', ['storage', 'final_commit'])
def test_retry_uses_saved_manifest_and_releases_write_block(pg, failure):
    async def scenario():
        company = pg.ids['company_a']
        root = f'company_images/company_{company}/'
        request = body(pg)
        request.file_path = root + 'tea/'
        async with pg.sessions() as session:
            await __create_image(request, pg.ids['admin_a'], session)
        survivor = body(pg)
        survivor.file_path = root + 'other/'
        async with pg.sessions() as session:
            await __create_image(survivor, pg.ids['admin_a'], session)
        keys = [request.file_path + request.file_name, root + 'tea/orphan']
        storage = SimpleNamespace(get_objects_by_dir_name=AsyncMock(return_value={key: 1 for key in keys}),
                                  delete_recorded_keys=AsyncMock())
        if failure == 'storage':
            storage.delete_recorded_keys.side_effect = HTTPException(503, 'Unavailable')
        folder = SimpleNamespace(company_id=company, dir_path=root, dir_name='tea/')
        async with pg.sessions() as session:
            if failure == 'final_commit':
                commits = 0
                def fail_second(_):
                    nonlocal commits
                    commits += 1
                    if commits == 2:
                        raise RuntimeError('Commit failed')
                event.listen(session.sync_session, 'before_commit', fail_second)
            with pytest.raises((HTTPException, RuntimeError)):
                await delete_image_directory(session, folder, storage)
        async with pg.sessions() as session:
            operation = await session.scalar(select(StorageDeleteDB))
            assert operation.status == 'pending'
            operation_id = operation.operation_id
            assert set((await session.scalars(select(ImageDB.image_id))).all()) == {survivor.image_id}
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await __create_image(body(pg), pg.ids['admin_a'], session)
            assert error.value.status_code == 409
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await __update_image_by_id({'file_path': root+'tea/'}, survivor.image_id, session)
            assert error.value.status_code == 409
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await rename_image_directory(session, SimpleNamespace(company_id=company, dir_path=root,
                    old_dir_name='other/', new_dir_name='tea/'), storage)
            assert error.value.status_code == 409
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await retry_directory_delete(session, pg.ids['company_b'], operation_id, storage)
            assert error.value.status_code == 404
        # A newly appeared, unrecorded object must not be included in the retry.
        storage.get_objects_by_dir_name.return_value = {root + 'tea/new.png': 1}
        storage.delete_recorded_keys.side_effect = None
        async with pg.sessions() as session:
            assert await delete_image_directory(session, folder, storage) == [request.image_id]
        storage.get_objects_by_dir_name.assert_awaited_once()
        assert storage.delete_recorded_keys.await_args.args == (sorted(keys), company)
        count = storage.delete_recorded_keys.await_count
        async with pg.sessions() as session:
            await retry_directory_delete(session, company, operation_id, storage)
        assert storage.delete_recorded_keys.await_count == count
        async with pg.sessions() as session:
            await __create_image(body(pg), pg.ids['admin_a'], session)
        async with pg.sessions() as session:
            assert (await session.scalar(select(StorageDeleteDB))).status == 'done'
    asyncio.run(scenario())


def test_concurrent_retries_delete_once(pg):
    async def scenario():
        company = pg.ids['company_a']
        async with pg.sessions() as session, session.begin():
            operation = StorageDeleteDB(company_id=company, prefix=f'company_images/company_{company}/tea/',
                                        keys=[], image_ids=[])
            session.add(operation)
            await session.flush()
            operation_id = operation.operation_id
        storage = SimpleNamespace(delete_recorded_keys=AsyncMock())
        async def retry():
            async with pg.sessions() as session:
                return await retry_directory_delete(session, company, operation_id, storage)
        assert all(result['status'] == 'done' for result in await asyncio.gather(retry(), retry()))
        storage.delete_recorded_keys.assert_awaited_once()
    asyncio.run(scenario())


def test_pending_upload_blocks_deletion_before_storage(pg):
    async def scenario():
        company = pg.ids['company_a']
        root = f'company_images/company_{company}/'
        request = body(pg)
        request.file_path = root + 'tea/'
        async with pg.sessions() as session:
            await __create_image(request, pg.ids['admin_a'], session, pending_upload=True)
        storage = SimpleNamespace(get_objects_by_dir_name=AsyncMock(), delete_recorded_keys=AsyncMock())
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await delete_image_directory(session, SimpleNamespace(company_id=company, dir_path=root, dir_name='tea/'), storage)
            assert error.value.status_code == 409
        storage.get_objects_by_dir_name.assert_not_awaited()
        storage.delete_recorded_keys.assert_not_awaited()
    asyncio.run(scenario())
