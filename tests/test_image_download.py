import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from botocore.exceptions import ClientError
from image import api_handlers as api
from s3_directory.storage.s3client import S3Client


def setup_api(monkeypatch, *, allowed=True, foreign=False, missing=False):
    company = uuid4()
    image = SimpleNamespace(image_id=uuid4(), company_id=uuid4() if foreign else company,
                            file_path=f'company_images/company_{company}/', file_name='чай.png')
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=SimpleNamespace(
        is_owner=allowed, is_admin=False, is_moderator=False)))
    monkeypatch.setattr(api, '__get_image_by_id', AsyncMock(return_value=None if missing else image))
    download = AsyncMock(return_value=b'image data')
    monkeypatch.setattr(api, 'S3Client', lambda: SimpleNamespace(download_image=download))
    return company, image, download


def call(company, image, filename='image.png'):
    return asyncio.run(api.download_image_proxy(image.image_id, company, filename,
        cur_user=SimpleNamespace(user_id=uuid4()), db=object()))


def test_download_uses_database_key_and_safe_unicode_filename(monkeypatch):
    company, image, download = setup_api(monkeypatch)
    result = call(company, image, 'чай\r\nX-Test: injected.png')
    assert result.body == b'image data'
    download.assert_awaited_once_with(image.file_path, image.file_name, company)
    assert '\r' not in result.headers['content-disposition']
    assert '\n' not in result.headers['content-disposition']
    assert "filename*=UTF-8''%D1%87" in result.headers['content-disposition']
    assert result.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('options,status', [({'allowed': False},403), ({'foreign': True},404), ({'missing': True},404)])
def test_download_rejects_unauthorized_image_before_storage(monkeypatch, options, status):
    company, image, download = setup_api(monkeypatch, **options)
    with pytest.raises(HTTPException) as error:
        call(company, image)
    assert error.value.status_code == status
    download.assert_not_awaited()


def test_storage_error_status_is_not_replaced_with_500(monkeypatch):
    company, image, download = setup_api(monkeypatch)
    download.side_effect = HTTPException(503, 'Storage temporarily unavailable')
    with pytest.raises(HTTPException) as error:
        call(company, image)
    assert error.value.status_code == 503


def test_legacy_url_only_request_is_rejected_without_storage(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    company, _, download = setup_api(monkeypatch)
    app = FastAPI()
    app.add_api_route('/image/download', api.download_image_proxy)
    app.dependency_overrides[api.__get_user_from_token] = lambda: SimpleNamespace(user_id=uuid4())
    app.dependency_overrides[api.get_db] = lambda: object()
    with TestClient(app) as client:
        result = client.get('/image/download', params={
            'company_id':str(company), 'image_url':'http://127.0.0.1/private'})
    assert result.status_code == 422
    download.assert_not_awaited()


class Body:
    def __init__(self, data):
        self.data = data
        self.closed = False
    async def __aenter__(self): return self
    async def __aexit__(self, *args): self.closed = True
    async def read(self, size):
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk


def setup_storage(monkeypatch, data=b'abc', length=3, error=None):
    body = Body(data)
    get = AsyncMock(return_value={'Body':body, 'ContentLength':length}, side_effect=error)
    @asynccontextmanager
    async def connection(self): yield SimpleNamespace(get_object=get)
    monkeypatch.setattr(S3Client, '_S3Client__get_client', connection)
    return S3Client('test-only'), body, get


@pytest.mark.parametrize('path,name', [('http://localhost/', 'a.png'), ('company_images/company_other/', 'a.png'),
                                     ('ROOT../', 'a.png'), ('ROOT', '../a.png')])
def test_bad_key_never_contacts_storage(monkeypatch, path, name):
    company = uuid4()
    service, _, get = setup_storage(monkeypatch)
    path = path.replace('ROOT', f'company_images/company_{company}/')
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.download_image(path, name, company))
    assert error.value.status_code == 422
    get.assert_not_awaited()


@pytest.mark.parametrize('length,data,status', [(3,b'abc',200), (9,b'abc',413), (0,b'123456789',413)])
def test_size_bound_and_body_closed(monkeypatch, length, data, status):
    from s3_directory.storage import s3client
    monkeypatch.setattr(s3client, 'QUOTA_IMAGE_SIZE', 8)
    service, body, get = setup_storage(monkeypatch, data, length)
    company = uuid4()
    path = f'company_images/company_{company}/'
    if status == 200:
        assert asyncio.run(service.download_image(path, 'a.png', company)) == data
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(service.download_image(path, 'a.png', company))
        assert error.value.status_code == status
    assert body.closed
    get.assert_awaited_once_with(Bucket='test-only', Key=path+'a.png')


@pytest.mark.parametrize('code,status', [('NoSuchKey',404), ('AccessDenied',503)])
def test_storage_failures_are_sanitized(monkeypatch, code, status):
    service, _, _ = setup_storage(monkeypatch, error=ClientError(
        {'Error': {'Code':code, 'Message':'private storage details'}}, 'GetObject'))
    company = uuid4()
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.download_image(f'company_images/company_{company}/', 'a.png', company))
    assert error.value.status_code == status
    assert 'private' not in error.value.detail
