import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_s3_listing import storage


def test_delete_always_passes_exact_version(monkeypatch):
    client = SimpleNamespace(delete_object=AsyncMock())
    service = storage(monkeypatch, client)
    company = uuid4()
    key = f'company_images/company_{company}/old/a.png'
    asyncio.run(service.delete_exact_version(key, 'old-version', company))
    client.delete_object.assert_awaited_once_with(Bucket='test-bucket', Key=key, VersionId='old-version')


@pytest.mark.parametrize('version', [None, '', 'null'])
def test_unversioned_delete_is_rejected(monkeypatch, version):
    client = SimpleNamespace(delete_object=AsyncMock())
    service = storage(monkeypatch, client)
    company = uuid4()
    with pytest.raises(HTTPException):
        asyncio.run(service.delete_exact_version(f'company_images/company_{company}/a.png', version, company))
    client.delete_object.assert_not_awaited()
