"""Refreshing gallery URLs must never authorize overwriting stored images."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from image import api_handlers as api


def setup_refresh(monkeypatch, *, allowed=True, exists=True):
    company_id = uuid4()
    root = f'company_images/company_{company_id}/'
    images = [SimpleNamespace(image_id=uuid4(), company_id=company_id,
                             file_path=root + path, file_name='photo.png')
              for path in ('tea/', 'tea/nested/', 'tea-old/', 'other/tea/')]
    storage = SimpleNamespace(
        generate_get_presigned_url=AsyncMock(return_value='https://example.test/read'),
        generate_put_presigned_url=AsyncMock())
    monkeypatch.setattr(api, 'S3Client', lambda: storage)
    monkeypatch.setattr(api, '__get_company_by_id', AsyncMock(return_value=object() if exists else None))
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=SimpleNamespace(
        is_owner=allowed, is_admin=False, is_moderator=False)))
    monkeypatch.setattr(api, '__get_images_by_company_id', AsyncMock(return_value=images))
    return company_id, root, images, storage


def refresh(company_id, folder):
    return asyncio.run(api.refresh_folder_urls(
        company_id=company_id, folder_path=folder,
        cur_user=SimpleNamespace(user_id=uuid4()), db=object()))


@pytest.mark.parametrize('trailing_slash', ['', '/'])
def test_refresh_issues_read_urls_only_for_folder_and_descendants(monkeypatch, trailing_slash):
    company_id, root, images, storage = setup_refresh(monkeypatch)
    result = refresh(company_id, root + 'tea' + trailing_slash)
    assert set(result['urls']) == {image.image_id for image in images[:2]}
    assert storage.generate_get_presigned_url.await_count == 2
    for image, call in zip(images[:2], storage.generate_get_presigned_url.await_args_list):
        assert call.kwargs == dict(file_path=image.file_path, file_name='photo.png', company_id=company_id)
    storage.generate_put_presigned_url.assert_not_called()


@pytest.mark.parametrize('allowed,exists,status', [(False, True, 403), (True, False, 404)])
def test_refresh_checks_access_before_storage(monkeypatch, allowed, exists, status):
    company_id, root, _, storage = setup_refresh(monkeypatch, allowed=allowed, exists=exists)
    with pytest.raises(HTTPException) as error:
        refresh(company_id, root)
    assert error.value.status_code == status
    storage.generate_get_presigned_url.assert_not_called()
    storage.generate_put_presigned_url.assert_not_called()


def test_refresh_propagates_storage_failure_without_write_fallback(monkeypatch):
    company_id, root, _, storage = setup_refresh(monkeypatch)
    storage.generate_get_presigned_url.side_effect = HTTPException(503, 'Storage temporarily unavailable')
    with pytest.raises(HTTPException) as error:
        refresh(company_id, root)
    assert error.value.status_code == 503
    storage.generate_put_presigned_url.assert_not_called()
