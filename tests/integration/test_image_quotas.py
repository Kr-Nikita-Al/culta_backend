import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from db import ImageDB
from image.actions.create_image_action import __create_image
from image.interface_request import CreateImageRequest
from image import quotas

pytestmark = pytest.mark.integration


def body(pg, size=10):
    return CreateImageRequest(image_id=uuid4(), company_id=pg.ids['company_a'],
        title='test.png', file_name=f'{uuid4()}.png', file_path='company_images/',
        size=size, width=1, height=1, type_col='', image_type='', resolution='',
        tags='', order_number=0, is_hidden=False,
        company_group_id='00000000-0000-0000-0000-000000000000')


async def create(pg, size=10, upload=None):
    async with pg.sessions() as session:
        try:
            await __create_image(body(pg, size), pg.ids['admin_a'], session, before_commit=upload)
            return 200
        except HTTPException as exc:
            return exc.status_code


def test_parallel_uploads_cannot_take_last_slot_twice(pg, monkeypatch):
    monkeypatch.setattr(quotas, 'QUOTA_COUNT_IMAGES_BY_COMPANY', 2)
    calls = []
    async def upload():
        calls.append(True)
    async def scenario():
        assert await create(pg) == 200
        assert sorted(await asyncio.gather(create(pg, upload=upload), create(pg, upload=upload))) == [200, 422]
    asyncio.run(scenario())
    assert len(calls) == 1
    with pg.engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ImageDB)) == 2


def test_pending_urls_reserve_total_bytes(pg, monkeypatch):
    monkeypatch.setattr(quotas, 'QUOTA_STORAGE_SIZE', 15)
    async def scenario():
        assert sorted(await asyncio.gather(create(pg), create(pg))) == [200, 422]
        assert await create(pg, 5) == 200
        assert await create(pg, 1) == 422
    asyncio.run(scenario())


def test_storage_failure_releases_reservation(pg, monkeypatch):
    monkeypatch.setattr(quotas, 'QUOTA_COUNT_IMAGES_BY_COMPANY', 1)
    async def fail():
        raise RuntimeError('Storage failed')
    async def scenario():
        with pytest.raises(RuntimeError, match='Storage failed'):
            await create(pg, upload=fail)
        assert await create(pg) == 200
    asyncio.run(scenario())


@pytest.mark.parametrize('size', [0, -1, float('nan'), float('inf'), 0.5, 2*1024*1024+1])
def test_invalid_size_rejected_before_storage(pg, size):
    async def scenario():
        async with pg.sessions() as session, session.begin():
            with pytest.raises(HTTPException) as exc:
                await quotas.reserve_image_quota(session, pg.ids['company_a'], size)
            assert exc.value.status_code == 422
    asyncio.run(scenario())
