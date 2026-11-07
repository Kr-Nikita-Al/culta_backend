import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from s3_directory.storage.s3client import S3Client


def storage(monkeypatch, client):
    @asynccontextmanager
    async def connection(self): yield client
    monkeypatch.setattr(S3Client,'_S3Client__get_client',connection)
    return S3Client('test-bucket')


def test_all_pages_and_exact_directory_prefix(monkeypatch):
    prefix='company_images/company_test/'
    requested=[]
    class Pages:
        async def paginate(self,**kwargs):
            requested.append(kwargs)
            yield {'Contents':[{'Key':prefix+str(i),'Size':i} for i in range(1000)]}
            yield {}
            yield {'Contents':[{'Key':prefix+'last.jpg','Size':123}]}
    service=storage(monkeypatch,SimpleNamespace(get_paginator=lambda name:Pages()))
    result=asyncio.run(service.get_objects_by_dir_name(prefix))
    assert len(result)==1001
    assert result[prefix+'last.jpg']==123
    assert requested==[{'Bucket':'test-bucket','Prefix':prefix}]
    with pytest.raises(HTTPException): asyncio.run(service.get_objects_by_dir_name(''))


def test_directory_boundary_is_not_substring(monkeypatch):
    service=storage(monkeypatch,SimpleNamespace())
    listing=AsyncMock(return_value={})
    monkeypatch.setattr(service,'get_all_objects',listing)
    asyncio.run(service.get_objects_by_dir_name('company_images/company_a'))
    listing.assert_awaited_once_with(prefix='company_images/company_a/')


@pytest.mark.parametrize('code',['404','NoSuchKey','AccessDenied'])
def test_exact_metadata_distinguishes_missing_from_denied(monkeypatch,code):
    head=AsyncMock(side_effect=ClientError({'Error':{'Code':code}},'HeadObject'))
    service=storage(monkeypatch,SimpleNamespace(head_object=head))
    if code=='AccessDenied':
        with pytest.raises(HTTPException) as error: asyncio.run(service.get_object_metadata('image.jpg'))
        assert error.value.status_code==503
    else: assert asyncio.run(service.get_object_metadata('image.jpg'))=={}
    head.assert_awaited_once_with(Bucket='test-bucket',Key='image.jpg')


def test_signed_url_uses_exact_head_not_list(monkeypatch):
    client=SimpleNamespace(head_object=AsyncMock(return_value={'ContentLength':42}),generate_presigned_url=AsyncMock(return_value='signed-url'))
    service=storage(monkeypatch,client)
    assert asyncio.run(service.generate_get_presigned_url('images/','a.jpg'))=='signed-url'
    client.head_object.assert_awaited_once_with(Bucket='test-bucket',Key='images/a.jpg')


def test_upload_url_signs_exact_size_and_checks_entire_company(monkeypatch):
    from uuid import UUID
    from urllib.parse import urlparse, parse_qs
    from s3_directory.storage import s3client as module
    company=UUID('00000000-0000-4000-8000-000000000002')
    root=f'company_images/company_{company}/'
    folder=root+'nested/'
    monkeypatch.setattr(module,'CONFIG_S3CLIENT',dict(endpoint_url='https://example.test',
        aws_access_key_id='test-only',aws_secret_access_key='test-only',region_name='ru-central1'))
    service=S3Client('test-bucket')
    listing=AsyncMock(return_value={folder:0})
    monkeypatch.setattr(service,'get_objects_by_dir_name',listing)
    # Real SDK signing, no request to the storage service.
    url=asyncio.run(service.generate_put_presigned_url(folder,'photo.png',42,company))
    assert 'content-length' in parse_qs(urlparse(url).query)['X-Amz-SignedHeaders'][0].split(';')
    assert 'if-none-match' in parse_qs(urlparse(url).query)['X-Amz-SignedHeaders'][0].split(';')
    assert [call.kwargs['dir_name'] for call in listing.await_args_list] == [folder,root]


@pytest.mark.parametrize('size',[None,0,-1,float('nan'),float('inf'),0.5])
def test_invalid_file_sizes_fail_closed(size):
    from s3_directory.actions.check_size_limits_action import check_size_limits
    assert not check_size_limits({},size)
