import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError
from s3_directory.storage.s3client import S3Client


@pytest.mark.parametrize('version', ['source-v1', 'null', None])
def test_copy_pins_source_version_and_records_destination(version):
    client = SimpleNamespace(head_object=AsyncMock(return_value={'VersionId':version, 'ETag':'"etag"'}),
        copy_object=AsyncMock(return_value={'ResponseMetadata':{'HTTPStatusCode':200}, 'VersionId':'destination-v2'}))
    pair = {'source':'old/a.png', 'destination':'new/a.png'}
    prepared = []
    async def prepare(plan):
        client.copy_object.assert_not_awaited()
        prepared.extend(plan)
    result = asyncio.run(S3Client('test-only')._copy_versioned_plan(client, [pair], prepare))
    expected = {**pair, **({'source_version':version} if version not in (None, 'null') else {})}
    assert prepared == [expected]
    assert result == [{**expected, 'destination_version':'destination-v2'}]
    source = {'Bucket':'test-only', 'Key':'old/a.png'}
    if version == 'source-v1': source['VersionId'] = version
    client.copy_object.assert_awaited_once_with(Bucket='test-only', Key='new/a.png',
        CopySource=source, CopySourceIfMatch='"etag"')


def test_missing_destination_version_is_not_invented():
    client = SimpleNamespace(head_object=AsyncMock(return_value={}),
        copy_object=AsyncMock(return_value={'ResponseMetadata':{'HTTPStatusCode':200}, 'VersionId':'null'}))
    pair = {'source':'old/a.png', 'destination':'new/a.png'}
    assert asyncio.run(S3Client('test-only')._copy_versioned_plan(client, [pair], None)) == [pair]


def test_failed_head_prevents_all_copying_and_journaling():
    client = SimpleNamespace(head_object=AsyncMock(side_effect=[{'VersionId':'v1'},
        ClientError({'Error':{'Code':'AccessDenied'}}, 'HeadObject')]), copy_object=AsyncMock())
    prepare = AsyncMock()
    with pytest.raises(ClientError):
        asyncio.run(S3Client('test-only')._copy_versioned_plan(client,
            [{'source':'old/a', 'destination':'new/a'}, {'source':'old/b', 'destination':'new/b'}], prepare))
    prepare.assert_not_awaited()
    client.copy_object.assert_not_awaited()


def test_failed_copy_does_not_change_prepared_manifest():
    pair = {'source':'old/a', 'destination':'new/a'}
    client = SimpleNamespace(head_object=AsyncMock(return_value={'VersionId':'v1'}),
        copy_object=AsyncMock(side_effect=ClientError({'Error':{'Code':'PreconditionFailed'}}, 'CopyObject')))
    prepare = AsyncMock()
    with pytest.raises(ClientError):
        asyncio.run(S3Client('test-only')._copy_versioned_plan(client, [pair], prepare))
    prepare.assert_awaited_once_with([{**pair, 'source_version':'v1'}])
