import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update, event
from sqlalchemy.exc import DBAPIError
from db import ImageDB, StorageMoveDB
from image.actions.create_image_action import __create_image
from image.actions import update_image_action as action
from tests.integration.test_image_quotas import body

pytestmark = pytest.mark.integration


async def seed(pg):
    request = body(pg)
    async with pg.sessions() as session:
        await __create_image(request, pg.ids['admin_a'], session)
    return request


@pytest.mark.parametrize('failure', ['none', 'copy', 'commit', 'validation', 'cancel'])
def test_move_keeps_original_on_every_failure(pg, monkeypatch, failure):
    objects = {}
    async def copy(**kwargs):
        await kwargs['before_copy']([{'source':kwargs['old_file_path'] + kwargs['file_name'],
                                     'destination':kwargs['new_file_path'] + kwargs['file_name']}])
        if failure == 'copy':
            raise HTTPException(503, 'Storage unavailable')
        if failure == 'cancel':
            raise asyncio.CancelledError()
        objects[kwargs['new_file_path'] + kwargs['file_name']] = objects[kwargs['old_file_path'] + kwargs['file_name']]
    storage = AsyncMock(side_effect=copy)
    monkeypatch.setattr(action, 'get_storage', lambda: SimpleNamespace(update_file_place_object=storage))
    async def scenario():
        image = await seed(pg)
        source = image.file_path + image.file_name
        objects[source] = b'original'
        target = image.file_path + 'target/'
        params = {'file_path':target}
        if failure == 'validation':
            params['title'] = 'x' * 101  # DB column limit: reject before copying.
        async with pg.sessions() as session:
            if failure == 'commit':
                def fail_commit(_): raise RuntimeError('Commit unavailable')
                event.listen(session.sync_session, 'before_commit', fail_commit)
            if failure == 'none':
                assert await action.__update_image_by_id(params, image.image_id, session) == image.image_id
            else:
                with pytest.raises((HTTPException, RuntimeError, DBAPIError, asyncio.CancelledError)):
                    await action.__update_image_by_id(params, image.image_id, session)
        async with pg.sessions() as session:
            path = await session.scalar(select(ImageDB.file_path).where(ImageDB.image_id == image.image_id))
            assert path == (target if failure == 'none' else image.file_path)
            assert objects[path + image.file_name] == b'original'
            journal = (await session.scalars(select(StorageMoveDB))).all()
            assert len(journal) == (0 if failure == 'validation' else 1)
            if journal:
                assert journal[0].status == ('committed' if failure == 'none' else 'pending')
                assert journal[0].source_key == source
                assert journal[0].destination_key == target + image.file_name
                assert journal[0].image_id == image.image_id
                assert journal[0].company_id == image.company_id
                assert journal[0].copied_keys == [{'source':source, 'destination':target + image.file_name}]
        assert objects[source] == b'original'
        if failure == 'validation': storage.assert_not_awaited()
    asyncio.run(scenario())


@pytest.mark.parametrize('change', ['same_path', 'title', 'file_name', 'used'])
def test_metadata_updates_do_not_move_storage(pg, monkeypatch, change):
    storage = AsyncMock()
    monkeypatch.setattr(action, 'get_storage', lambda: SimpleNamespace(update_file_place_object=storage))
    async def scenario():
        image = await seed(pg)
        params = {'file_path':image.file_path} if change == 'same_path' else {'title':'New title'}
        if change == 'file_name': params = {'file_name':'different.png'}
        if change == 'used':
            async with pg.sessions() as session, session.begin():
                await session.execute(update(ImageDB).where(ImageDB.image_id == image.image_id).values(is_used=True))
        async with pg.sessions() as session:
            if change in ('file_name', 'used'):
                with pytest.raises(HTTPException) as error:
                    await action.__update_image_by_id(params, image.image_id, session)
                assert error.value.status_code == (422 if change == 'file_name' else 409)
            else:
                await action.__update_image_by_id(params, image.image_id, session)
        storage.assert_not_awaited()
        async with pg.sessions() as session:
            assert (await session.scalars(select(StorageMoveDB))).all() == []
    asyncio.run(scenario())


def test_parallel_moves_read_the_latest_locked_path(pg, monkeypatch):
    calls = []
    async def copy(**kwargs):
        await kwargs['before_copy']([{'source':kwargs['old_file_path'] + kwargs['file_name'],
                                     'destination':kwargs['new_file_path'] + kwargs['file_name']}])
        calls.append(kwargs)
        await asyncio.sleep(0.01)
    monkeypatch.setattr(action, 'get_storage', lambda: SimpleNamespace(update_file_place_object=copy))
    async def scenario():
        image = await seed(pg)
        async def move(path):
            async with pg.sessions() as session:
                await action.__update_image_by_id({'file_path':path}, image.image_id, session)
        await asyncio.gather(move(image.file_path+'a/'), move(image.file_path+'b/'))
        assert calls[0]['old_file_path'] == image.file_path
        assert calls[1]['old_file_path'] == calls[0]['new_file_path']
        async with pg.sessions() as session:
            assert await session.scalar(select(ImageDB.file_path)) == calls[1]['new_file_path']
            journal = (await session.scalars(select(StorageMoveDB))).all()
            assert len(journal) == 2
            assert len({row.operation_id for row in journal}) == 2
    asyncio.run(scenario())


@pytest.mark.parametrize('failed', [False, True])
def test_journal_retains_exact_versions(pg, monkeypatch, failed):
    async def copy(**kwargs):
        pair = {'source':kwargs['old_file_path'] + kwargs['file_name'],
                'destination':kwargs['new_file_path'] + kwargs['file_name'], 'source_version':'source-v1'}
        await kwargs['before_copy']([pair])
        if failed: raise HTTPException(503, 'Copy failed')
        return [{**pair, 'destination_version':'destination-v2'}]
    monkeypatch.setattr(action, 'get_storage', lambda: SimpleNamespace(update_file_place_object=copy))
    async def scenario():
        image = await seed(pg)
        async with pg.sessions() as session:
            if failed:
                with pytest.raises(HTTPException):
                    await action.__update_image_by_id({'file_path':image.file_path+'target/'}, image.image_id, session)
            else:
                await action.__update_image_by_id({'file_path':image.file_path+'target/'}, image.image_id, session)
        async with pg.sessions() as session:
            row = await session.scalar(select(StorageMoveDB))
            assert row.status == ('pending' if failed else 'committed')
            assert row.copied_keys[0]['source_version'] == 'source-v1'
            assert row.copied_keys[0].get('destination_version') == (None if failed else 'destination-v2')
    asyncio.run(scenario())


def test_two_images_cannot_move_into_same_key(pg, monkeypatch):
    calls = []
    async def copy(**kwargs):
        calls.append(kwargs)
        await kwargs['before_copy']([{'source':kwargs['old_file_path']+'shared.png',
                                     'destination':kwargs['new_file_path']+'shared.png'}])
        await asyncio.sleep(0.01)
    monkeypatch.setattr(action, 'get_storage', lambda: SimpleNamespace(update_file_place_object=copy))
    async def scenario():
        ids = []
        for folder in ('one/', 'two/'):
            request = body(pg)
            request.file_path = 'company_images/' + folder
            request.file_name = 'shared.png'
            async with pg.sessions() as session:
                await __create_image(request, pg.ids['admin_a'], session)
            ids.append(request.image_id)
        async def move(image_id):
            async with pg.sessions() as session:
                try:
                    await action.__update_image_by_id({'file_path':'company_images/target/'}, image_id, session)
                    return 200
                except HTTPException as error:
                    return error.status_code
        assert sorted(await asyncio.wait_for(asyncio.gather(*(move(i) for i in ids)), timeout=10)) == [200, 409]
    asyncio.run(scenario())
    assert len(calls) == 1
