import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from s3_directory.storage.s3client import S3Client


def setup(monkeypatch):
    company = uuid4()
    root = f'company_images/company_{company}/'
    client = SimpleNamespace(head_object=AsyncMock(return_value={}), copy_object=AsyncMock(return_value={'ResponseMetadata': {'HTTPStatusCode': 200}}),
                             delete_object=AsyncMock())
    @asynccontextmanager
    async def connection(self): yield client
    monkeypatch.setattr(S3Client, '_S3Client__get_client', connection)
    storage = S3Client('test-only')
    listing = AsyncMock(return_value={root+'a.png': 10, root+'target/': 0})
    monkeypatch.setattr(storage, 'get_objects_by_dir_name', listing)
    return company, root, storage, client, listing


def test_same_directory_is_noop_without_storage_requests(monkeypatch):
    company, root, storage, client, listing = setup(monkeypatch)
    asyncio.run(storage.update_file_place_object(root, root, 'a.png', company))
    listing.assert_not_awaited()
    client.copy_object.assert_not_awaited()
    client.delete_object.assert_not_awaited()


def test_existing_destination_is_not_overwritten(monkeypatch):
    company, root, storage, client, listing = setup(monkeypatch)
    listing.return_value[root+'target/a.png'] = 20
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.update_file_place_object(root, root+'target/', 'a.png', company))
    assert error.value.status_code == 409
    client.copy_object.assert_not_awaited()
    client.delete_object.assert_not_awaited()


@pytest.mark.parametrize('path,name', [('company_images/company_other/', 'a.png'), ('../', 'a.png'),
                                     ('ROOT../', 'a.png'), ('ROOT', '../a.png'), ('ROOT', 'bad\\a.png')])
def test_invalid_move_never_touches_storage(monkeypatch, path, name):
    company, root, storage, client, listing = setup(monkeypatch)
    path = path.replace('ROOT', root)
    with pytest.raises(HTTPException) as error:
        asyncio.run(storage.update_file_place_object(path, path, name, company))
    assert error.value.status_code == 422
    listing.assert_not_awaited()
    client.copy_object.assert_not_awaited()
    client.delete_object.assert_not_awaited()


@pytest.mark.parametrize('status', [200, 500])
def test_source_retained_even_after_successful_copy(monkeypatch, status):
    company, root, storage, client, _ = setup(monkeypatch)
    client.copy_object.return_value['ResponseMetadata']['HTTPStatusCode'] = status
    call = storage.update_file_place_object(root, root+'target/', 'a.png', company)
    if status == 200:
        asyncio.run(call)
        client.delete_object.assert_not_awaited()
    else:
        with pytest.raises(HTTPException):
            asyncio.run(call)
        client.delete_object.assert_not_awaited()
    client.copy_object.assert_awaited_once_with(Bucket='test-only', Key=root+'target/a.png',
        CopySource={'Bucket':'test-only', 'Key':root+'a.png'})


@pytest.mark.parametrize('fails', [False, True])
def test_copy_waits_for_durable_intent(monkeypatch, fails):
    company, root, storage, client, _ = setup(monkeypatch)
    async def prepare(keys):
        client.copy_object.assert_not_awaited()
        assert keys == [{'source':root+'a.png', 'destination':root+'target/a.png'}]
        if fails:
            raise RuntimeError('Journal unavailable')
    call = storage.update_file_place_object(root, root+'target/', 'a.png', company, before_copy=prepare)
    if fails:
        with pytest.raises(RuntimeError): asyncio.run(call)
        client.copy_object.assert_not_awaited()
    else:
        asyncio.run(call)
        client.copy_object.assert_awaited_once()
    client.delete_object.assert_not_awaited()
