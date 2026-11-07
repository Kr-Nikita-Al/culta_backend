import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update, func

from db import ImageDB, ImageUploadReservationDB, CompanyDB, UserRoleDB, ProductCardDB
from image import upload_reservations as reservations, quotas
from image.actions.create_image_action import __create_image
from tests.integration.test_image_quotas import body

pytestmark = pytest.mark.integration


async def pending(pg, *, expired=True, company=None):
    request = body(pg)
    if company:
        request.company_id = company
    async with pg.sessions() as session:
        await __create_image(request, pg.ids['admin_a'], session, pending_upload=True)
    if expired:
        async with pg.sessions() as session, session.begin():
            await session.execute(update(ImageUploadReservationDB).where(
                ImageUploadReservationDB.image_id == request.image_id).values(
                    cleanup_after=datetime.now(timezone.utc) - timedelta(seconds=1)))
    return request


def storage(monkeypatch, *, exists=False, error=None):
    async def head(key):
        if error:
            raise error
        return {key: 10} if exists else {}
    mock = SimpleNamespace(get_object_metadata=AsyncMock(side_effect=head))
    monkeypatch.setattr(reservations, 'S3Client', lambda: mock)
    return mock


async def sweep(pg):
    async with pg.sessions() as session, session.begin():
        await session.execute(select(CompanyDB.company_id).where(CompanyDB.company_id == pg.ids['company_a']).with_for_update())
        await reservations.cleanup_expired_uploads(session, pg.ids['company_a'])


def test_missing_expired_upload_frees_last_slot_atomically(pg, monkeypatch):
    mock = storage(monkeypatch)
    monkeypatch.setattr(quotas, 'QUOTA_COUNT_IMAGES_BY_COMPANY', 1)
    async def scenario():
        old = await pending(pg)
        async with pg.sessions() as session:
            new = await __create_image(body(pg), pg.ids['admin_a'], session)
        async with pg.sessions() as session:
            assert (await session.scalars(select(ImageDB.image_id))).all() == [new.image_id]
            assert await session.scalar(select(func.count()).select_from(ImageUploadReservationDB)) == 0
        mock.get_object_metadata.assert_awaited_once_with(old.file_path + old.file_name)
    asyncio.run(scenario())


def test_existing_object_keeps_image_and_quota(pg, monkeypatch):
    storage(monkeypatch, exists=True)
    async def scenario():
        old = await pending(pg)
        await sweep(pg)
        async with pg.sessions() as session:
            assert await session.scalar(select(ImageDB.image_id)) == old.image_id
            assert await session.scalar(select(func.count()).select_from(ImageUploadReservationDB)) == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('error', [HTTPException(503, 'Unavailable'), TimeoutError()])
def test_storage_failure_keeps_reservation(pg, monkeypatch, error):
    storage(monkeypatch, error=error)
    async def scenario():
        old = await pending(pg)
        await sweep(pg)
        async with pg.sessions() as session:
            assert await session.scalar(select(ImageDB.image_id)) == old.image_id
            assert await session.scalar(select(ImageUploadReservationDB.image_id)) == old.image_id
    asyncio.run(scenario())


def test_fresh_legacy_and_other_company_are_untouched(pg, monkeypatch):
    mock = storage(monkeypatch)
    async def scenario():
        await pending(pg, expired=False)
        await pending(pg, company=pg.ids['company_b'])
        async with pg.sessions() as session:
            await __create_image(body(pg), pg.ids['admin_a'], session)
        await sweep(pg)
        async with pg.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(ImageDB)) == 3
            assert await session.scalar(select(func.count()).select_from(ImageUploadReservationDB)) == 2
        mock.get_object_metadata.assert_not_awaited()
    asyncio.run(scenario())


@pytest.mark.parametrize('kind', ['used', 'renamed', 'company', 'avatar', 'product'])
def test_referenced_or_changed_image_is_never_removed(pg, monkeypatch, kind):
    mock = storage(monkeypatch)
    async def scenario():
        old = await pending(pg)
        async with pg.sessions() as session, session.begin():
            if kind == 'used':
                await session.execute(update(ImageDB).values(is_used=True))
            elif kind == 'renamed':
                await session.execute(update(ImageDB).values(file_name='changed.png'))
            elif kind == 'company':
                await session.execute(update(CompanyDB).where(CompanyDB.company_id == old.company_id)
                                      .values(image_picture_id=old.image_id))
            elif kind == 'avatar':
                await session.execute(update(UserRoleDB).where(UserRoleDB.company_id == old.company_id)
                                      .values(avatar_id=old.image_id))
            else:
                await session.execute(update(ProductCardDB).where(ProductCardDB.company_id == old.company_id)
                                      .values(image_icon_id=old.image_id))
        await sweep(pg)
        async with pg.sessions() as session:
            assert await session.scalar(select(ImageDB.image_id)) == old.image_id
            assert await session.scalar(select(func.count()).select_from(ImageUploadReservationDB)) == 0
        mock.get_object_metadata.assert_not_awaited()
    asyncio.run(scenario())


def test_cleanup_skips_image_locked_by_an_editor(pg, monkeypatch):
    mock = storage(monkeypatch)
    async def scenario():
        old = await pending(pg)
        async with pg.sessions() as editor, editor.begin():
            await editor.execute(select(ImageDB).where(ImageDB.image_id == old.image_id).with_for_update(read=True))
            await sweep(pg)
            mock.get_object_metadata.assert_not_awaited()
        await sweep(pg)
        mock.get_object_metadata.assert_awaited_once()
    asyncio.run(scenario())


def test_parallel_cleanup_cannot_double_spend_freed_slot(pg, monkeypatch):
    storage(monkeypatch)
    monkeypatch.setattr(quotas, 'QUOTA_COUNT_IMAGES_BY_COMPANY', 1)
    async def create():
        async with pg.sessions() as session:
            try:
                await __create_image(body(pg), pg.ids['admin_a'], session)
                return 200
            except HTTPException as error:
                return error.status_code
    async def scenario():
        await pending(pg)
        assert sorted(await asyncio.gather(create(), create())) == [200, 422]
    asyncio.run(scenario())


def test_upload_marker_has_grace_and_rolls_back_with_image(pg, monkeypatch):
    mock = storage(monkeypatch)
    async def fail():
        raise RuntimeError('Signing failed')
    async def scenario():
        async with pg.sessions() as session:
            with pytest.raises(RuntimeError):
                await __create_image(body(pg), pg.ids['admin_a'], session,
                                     pending_upload=True, before_commit=fail)
        async with pg.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(ImageUploadReservationDB)) == 0
            assert await session.scalar(select(func.count()).select_from(ImageDB)) == 0
        before = datetime.now(timezone.utc)
        await pending(pg, expired=False)
        async with pg.sessions() as session:
            cleanup_after = await session.scalar(select(ImageUploadReservationDB.cleanup_after))
            assert cleanup_after >= before + timedelta(days=1, seconds=120)
        mock.get_object_metadata.assert_not_awaited()
    asyncio.run(scenario())


def test_failed_new_upload_rolls_back_cleanup_too(pg, monkeypatch):
    storage(monkeypatch)
    async def fail():
        raise RuntimeError('Upload failed')
    async def scenario():
        old = await pending(pg)
        async with pg.sessions() as session:
            with pytest.raises(RuntimeError):
                await __create_image(body(pg), pg.ids['admin_a'], session, before_commit=fail)
        async with pg.sessions() as session:
            assert (await session.scalars(select(ImageDB.image_id))).all() == [old.image_id]
            assert await session.scalar(select(ImageUploadReservationDB.image_id)) == old.image_id
    asyncio.run(scenario())
