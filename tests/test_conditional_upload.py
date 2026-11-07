import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from tests.test_s3_listing import storage


@pytest.mark.parametrize('code,status', [(None,200), ('PreconditionFailed',409),
    ('ConditionalRequestConflict',409), ('AccessDenied',503)])
def test_direct_upload_is_conditional_and_does_not_retry_unconditionally(monkeypatch, code, status):
    put = AsyncMock(side_effect=ClientError({'Error':{'Code':code,'Message':'internal'}}, 'PutObject') if code else None)
    service = storage(monkeypatch, SimpleNamespace(put_object=put))
    monkeypatch.setattr(service, 'get_objects_by_dir_name', AsyncMock(return_value={}))
    company = uuid4()
    path = f'company_images/company_{company}/'
    file = SimpleNamespace(size=3, content_type='image/png', read=AsyncMock(return_value=b'png'))
    call = service.upload_file(file, path, 'a.png', company)
    if status == 200:
        asyncio.run(call)
    else:
        with pytest.raises(HTTPException) as error: asyncio.run(call)
        assert error.value.status_code == status
        assert 'internal' not in error.value.detail
        if code == 'AccessDenied':
            assert error.value.detail == 'Storage write access denied'
    put.assert_awaited_once_with(Bucket='test-bucket', Key=path+'a.png', Body=b'png',
                                ContentType='image/png', IfNoneMatch='*')
