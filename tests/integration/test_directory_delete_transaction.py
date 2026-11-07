import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, event, update
from db import ImageDB, CompanyDB, ProductCardDB, UserRoleDB, StorageDeleteDB
from image.actions.create_image_action import __create_image
from image.directory_delete import delete_image_directory
from tests.integration.test_image_quotas import body

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('mode', ['ok', 'storage', 'commit', 'used', 'company_photo', 'product', 'avatar', 'busy'])
def test_directory_deletion_is_one_database_transaction(pg, mode):
    async def scenario():
        company = pg.ids['company_a']
        root = f'company_images/company_{company}/'
        ids = []
        for path in ['tea/', 'tea/nested/', 'tea-other/', 'other/tea/']:
            request = body(pg)
            request.file_path = root + path
            async with pg.sessions() as session:
                ids.append((await __create_image(request, pg.ids['admin_a'], session)).image_id)
        async with pg.sessions() as session, session.begin():
            if mode == 'used':
                await session.execute(update(ImageDB).where(ImageDB.image_id == ids[1]).values(is_used=True))
            if mode == 'company_photo':
                await session.execute(update(CompanyDB).where(CompanyDB.company_id == company).values(image_picture_id=ids[1]))
            if mode == 'product':
                await session.execute(update(ProductCardDB).where(ProductCardDB.company_id == company).values(image_icon_id=ids[1]))
            if mode == 'avatar':
                await session.execute(update(UserRoleDB).where(UserRoleDB.company_id == company).values(avatar_id=ids[1]))
        storage = SimpleNamespace(get_objects_by_dir_name=AsyncMock(return_value={root+'tea/orphan.png': 5}),
            delete_recorded_keys=AsyncMock(side_effect=HTTPException(503, 'Partial deletion') if mode == 'storage' else None))
        request = SimpleNamespace(company_id=company, dir_path=root, dir_name='tea/')
        async with pg.sessions() as editor:
            if mode == 'busy':
                await editor.scalar(select(ImageDB).where(ImageDB.image_id == ids[0]).with_for_update(read=True))
            async with pg.sessions() as session:
                if mode == 'commit':
                    def fail(_):
                        raise RuntimeError('Commit failed')
                    event.listen(session.sync_session, 'before_commit', fail)
                if mode == 'ok':
                    assert set(await delete_image_directory(session, request, storage)) == set(ids[:2])
                else:
                    with pytest.raises((HTTPException, RuntimeError)) as error:
                        await asyncio.wait_for(delete_image_directory(session, request, storage), 5)
                    if mode in ('used', 'company_photo', 'product', 'avatar', 'busy'):
                        assert error.value.status_code == 409
                        storage.delete_recorded_keys.assert_not_awaited()
            await editor.rollback()
        async with pg.sessions() as session:
            remaining = set((await session.scalars(select(ImageDB.image_id))).all())
            assert remaining == set(ids[2:] if mode in ('ok', 'storage') else ids)
            journal = (await session.scalars(select(StorageDeleteDB))).all()
            assert len(journal) == (1 if mode in ('ok', 'storage') else 0)
            if journal:
                assert journal[0].status == ('done' if mode == 'ok' else 'pending')
        if mode == 'commit':
            storage.delete_recorded_keys.assert_not_awaited()
    asyncio.run(scenario())
