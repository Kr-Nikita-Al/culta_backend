import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from image.directory_move import directory_prefixes
from s3_directory.storage.s3client import S3Client


@pytest.mark.parametrize('name', ['', '/', '../', 'a/b/', 'a\\b/', 'name'])
def test_directory_name_is_one_component(name):
    company = uuid4()
    with pytest.raises(HTTPException):
        directory_prefixes(company, f'company_images/company_{company}/', 'old/', name)


@pytest.mark.parametrize('mode', ['ok', 'collision', 'same', 'failure'])
def test_directory_copy_preserves_sources_and_prefix_boundaries(monkeypatch, mode):
    company = uuid4()
    root = f'company_images/company_{company}/'
    client = SimpleNamespace(head_object=AsyncMock(return_value={}), copy_object=AsyncMock(return_value={'ResponseMetadata':{'HTTPStatusCode':200}}),
                             delete_object=AsyncMock())
    @asynccontextmanager
    async def connection(self): yield client
    monkeypatch.setattr(S3Client, '_S3Client__get_client', connection)
    storage = S3Client('test-only')
    objects = {root+'old/a.png':10, root+'old/nested/b.png':10, root+'old-extra/c.png':10}
    if mode == 'collision': objects[root+'new/nested/existing.png'] = 10
    if mode == 'failure': client.copy_object.return_value['ResponseMetadata']['HTTPStatusCode'] = 500
    listing = AsyncMock(return_value=objects)
    monkeypatch.setattr(storage, 'get_objects_by_dir_name', listing)
    call = storage.rename_directory(root, 'old/', 'old/' if mode == 'same' else 'new/', company)
    if mode in ('collision', 'failure'):
        with pytest.raises(HTTPException) as error: asyncio.run(call)
        assert error.value.status_code == (409 if mode == 'collision' else 503)
    else:
        manifest = asyncio.run(call)
    client.delete_object.assert_not_awaited()
    if mode in ('collision', 'same'):
        client.copy_object.assert_not_awaited()
    if mode == 'same': listing.assert_not_awaited()
    if mode == 'ok':
        assert manifest == [{'source':root+'old/a.png', 'destination':root+'new/a.png'},
                            {'source':root+'old/nested/b.png', 'destination':root+'new/nested/b.png'}]
        assert [call.kwargs['Key'] for call in client.copy_object.await_args_list] == [root+'new/a.png', root+'new/nested/b.png']
