import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from image import api_handlers as api
from s3_directory.storage import S3Client


@pytest.mark.parametrize('storage_fails', [False, True])
def test_storage_error_preserves_database_row(monkeypatch, storage_fails):
    image_id, company_id = uuid4(), uuid4()
    image = SimpleNamespace(company_id=company_id, file_path='root/', file_name='image.png')
    monkeypatch.setattr(api, '__get_image_by_id', AsyncMock(return_value=image))
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=SimpleNamespace(is_admin=True, is_owner=False, is_moderator=False)))
    delete_row = AsyncMock(return_value=image_id)
    monkeypatch.setattr(api, '__delete_image', delete_row)

    async def delete_file(**kwargs):
        delete_row.assert_not_awaited()
        if storage_fails:
            raise HTTPException(403, 'Storage denied')

    monkeypatch.setattr(api, 'S3Client', lambda: SimpleNamespace(delete_file=delete_file))
    call = api.delete_image(image_id, object(), SimpleNamespace(user_id=uuid4()))
    if storage_fails:
        with pytest.raises(HTTPException):
            asyncio.run(call)
        delete_row.assert_not_awaited()
    else:
        assert asyncio.run(call).deleted_image_id == image_id
        delete_row.assert_awaited_once()


def test_missing_image_returns_404(monkeypatch):
    monkeypatch.setattr(api, '__get_image_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.delete_image(uuid4(), object(), SimpleNamespace(user_id=uuid4())))
    assert error.value.status_code == 404


@pytest.mark.parametrize('foreign', [False, True])
def test_delete_does_not_require_object_listing(monkeypatch, foreign):
    company_id = uuid4()
    client = SimpleNamespace(delete_object=AsyncMock())

    @asynccontextmanager
    async def get_client(self):
        yield client

    monkeypatch.setattr(S3Client, '_S3Client__get_client', get_client)
    storage = S3Client()
    path = f'company_images/company_{uuid4() if foreign else company_id}/'
    call = storage.delete_file(path, 'image.png', company_id)
    if foreign:
        with pytest.raises(HTTPException):
            asyncio.run(call)
        client.delete_object.assert_not_awaited()
    else:
        asyncio.run(call)
        client.delete_object.assert_awaited_once()
