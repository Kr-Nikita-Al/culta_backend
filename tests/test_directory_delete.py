import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from s3_directory.storage.s3client import S3Client


@pytest.mark.parametrize('mode', ['ok', 'empty', 'partial', 'listing_failure', 'foreign'])
def test_directory_deletion_batches_and_checks_results(monkeypatch, mode):
    company = uuid4()
    root = f'company_images/company_{company}/'
    prefix = root + 'tea/'
    async def pages(**kwargs):
        assert kwargs == {'Bucket': 'test-only', 'Prefix': prefix}
        if mode == 'empty':
            return
        yield {'Contents': [{'Key': prefix + str(i)} for i in range(1000)]}
        if mode == 'listing_failure':
            raise HTTPException(503, 'Listing failed')
        yield {'Contents': [{'Key': root + 'tea-other/a' if mode == 'foreign' else prefix + 'last'}]}
    result = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    if mode == 'partial':
        result['Errors'] = [{'Code': 'AccessDenied', 'Key': prefix + '0'}]
    client = SimpleNamespace(get_paginator=lambda name: SimpleNamespace(paginate=pages),
                             delete_objects=AsyncMock(return_value=result))
    @asynccontextmanager
    async def connection(self):
        yield client
    monkeypatch.setattr(S3Client, '_S3Client__get_client', connection)
    call = S3Client('test-only').delete_directory(root, 'tea/', company)
    if mode in ('partial', 'listing_failure', 'foreign'):
        with pytest.raises(HTTPException) as error:
            asyncio.run(call)
        assert error.value.status_code == 503
    else:
        asyncio.run(call)
    calls = client.delete_objects.await_args_list
    assert len(calls) == {'ok': 2, 'empty': 0, 'partial': 1, 'listing_failure': 0, 'foreign': 0}[mode]
    if mode == 'ok':
        assert [len(call.kwargs['Delete']['Objects']) for call in calls] == [1000, 1]
        assert all(obj['Key'].startswith(prefix) for call in calls for obj in call.kwargs['Delete']['Objects'])


@pytest.mark.parametrize('name', ['', '../', 'tea', 'tea/other/'])
def test_invalid_directory_never_connects(monkeypatch, name):
    connection = AsyncMock()
    monkeypatch.setattr(S3Client, '_S3Client__get_client', connection)
    company = uuid4()
    with pytest.raises(HTTPException) as error:
        asyncio.run(S3Client('test-only').delete_directory(f'company_images/company_{company}/', name, company))
    assert error.value.status_code == 422
    connection.assert_not_called()


@pytest.mark.parametrize('storage_failure', [False, True])
def test_api_deletes_only_exact_folder_after_storage_success(monkeypatch, storage_failure):
    import s3_directory.api_handlers as api
    import image.directory_delete as action
    company = uuid4()
    root = f'company_images/company_{company}/'
    role = SimpleNamespace(is_owner=True)
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=role))
    storage = SimpleNamespace(delete_directory=AsyncMock(side_effect=HTTPException(503, 'Incomplete') if storage_failure else None))
    monkeypatch.setattr(api, 'S3Client', lambda: storage)
    deletion = AsyncMock(return_value=[0, 1], side_effect=HTTPException(503, 'Incomplete') if storage_failure else None)
    monkeypatch.setattr(action, 'delete_image_directory', deletion)
    body = SimpleNamespace(company_id=company, dir_path=root, dir_name='tea/')
    call = api.delete_directory(body, object(), SimpleNamespace(user_id=uuid4()))
    if storage_failure:
        with pytest.raises(HTTPException):
            asyncio.run(call)
    else:
        assert asyncio.run(call) == {'deleted image id': [0, 1]}
    deletion.assert_awaited_once()
    assert deletion.await_args.args[1:] == (body, storage)


@pytest.mark.parametrize('mode', ['ok', 'partial', 'foreign'])
def test_recorded_keys_are_bounded_and_never_relisted(monkeypatch, mode):
    company = uuid4()
    root = f'company_images/company_{company}/'
    keys = [root + str(i) for i in range(1001)]
    if mode == 'foreign':
        keys.append('company_images/another/file')
    result = {'ResponseMetadata': {'HTTPStatusCode': 200}}
    if mode == 'partial':
        result['Errors'] = [{'Code': 'AccessDenied'}]
    client = SimpleNamespace(delete_objects=AsyncMock(return_value=result))
    @asynccontextmanager
    async def connection(self):
        yield client
    monkeypatch.setattr(S3Client, '_S3Client__get_client', connection)
    call = S3Client('test-only').delete_recorded_keys(keys, company)
    if mode != 'ok':
        with pytest.raises(HTTPException) as error:
            asyncio.run(call)
        assert error.value.status_code == (422 if mode == 'foreign' else 503)
    else:
        asyncio.run(call)
    calls = client.delete_objects.await_args_list
    assert len(calls) == {'ok': 2, 'partial': 1, 'foreign': 0}[mode]
    if mode == 'ok':
        assert [obj['Key'] for call in calls for obj in call.kwargs['Delete']['Objects']] == keys


@pytest.mark.parametrize('endpoint', ['pending_deletions', 'retry_deletion'])
def test_deletion_recovery_requires_staff_role(monkeypatch, endpoint):
    import s3_directory.api_handlers as api
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=SimpleNamespace(
        is_owner=False, is_admin=False, is_moderator=False)))
    kwargs = dict(company_id=uuid4(), db=object(), cur_user=SimpleNamespace(user_id=uuid4()))
    if endpoint == 'retry_deletion':
        kwargs['operation_id'] = uuid4()
    with pytest.raises(HTTPException) as error:
        asyncio.run(getattr(api, endpoint)(**kwargs))
    assert error.value.status_code == 403
