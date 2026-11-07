import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from db import ImageDB
from image.actions.create_image_action import __create_image
from tests.integration.test_image_quotas import body

pytestmark = pytest.mark.integration


def test_parallel_requests_reserve_one_key_once(pg):
    upload = AsyncMock()
    async def create():
        request = body(pg)
        request.file_name = 'shared.png'
        async with pg.sessions() as session:
            try:
                await __create_image(request, pg.ids['admin_a'], session, before_commit=upload, pending_upload=True)
                return 200
            except HTTPException as error:
                return error.status_code
    async def scenario():
        assert sorted(await asyncio.wait_for(asyncio.gather(create(), create()), timeout=10)) == [200, 409]
        async with pg.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(ImageDB)) == 1
    asyncio.run(scenario())
    upload.assert_awaited_once()


@pytest.mark.parametrize('variant', ['hidden', 'pending', 'split'])
def test_existing_keys_are_protected(pg, variant):
    upload = AsyncMock()
    async def scenario():
        first = body(pg)
        first.file_path = 'company_images/nested/'
        first.file_name = 'a.png'
        first.is_hidden = variant == 'hidden'
        async with pg.sessions() as session:
            await __create_image(first, pg.ids['admin_a'], session, pending_upload=variant == 'pending')
        second = body(pg)
        second.file_path = 'company_images/' if variant == 'split' else first.file_path
        second.file_name = 'nested/a.png' if variant == 'split' else first.file_name
        async with pg.sessions() as session:
            with pytest.raises(HTTPException) as error:
                await __create_image(second, pg.ids['admin_a'], session, before_commit=upload)
            assert error.value.status_code == 409
    asyncio.run(scenario())
    upload.assert_not_awaited()


def test_rollback_releases_key_for_retry(pg):
    async def fail(): raise RuntimeError('Upload failed')
    async def scenario():
        request = body(pg)
        async with pg.sessions() as session:
            with pytest.raises(RuntimeError):
                await __create_image(request, pg.ids['admin_a'], session, before_commit=fail)
        async with pg.sessions() as session:
            assert (await __create_image(request, pg.ids['admin_a'], session)).image_id == request.image_id
    asyncio.run(scenario())
