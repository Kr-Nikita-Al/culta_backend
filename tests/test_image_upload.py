import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from image.actions import create_image_action as action
from s3_directory.actions.check_file_path_put_action import check_file_path_put

COMPANY = UUID('00000000-0000-4000-8000-000000000002')
ROOT = f'company_images/company_{COMPANY}/'


@pytest.mark.parametrize('objects,path,name,expected', [
    ({}, ROOT, 'image.png', True),
    ({}, ROOT, 'photo.original.JPG', True),
    ({}, ROOT + 'missing/', 'image.png', False),
    ({ROOT + 'nested/': 0}, ROOT + 'nested/', 'image.png', True),
    ({}, 'company_images/company_other/', 'image.png', False),
    ({}, ROOT, 'image.exe', False),
    ({}, '', 'image.png', False),
    ({}, ROOT.rstrip('/'), 'image.png', False),
])
def test_upload_path(objects, path, name, expected):
    assert check_file_path_put(objects, path, name, COMPANY) is expected


@pytest.mark.parametrize('fails', [False, True])
def test_storage_upload_finishes_before_database_commit(monkeypatch, fails):
    transaction = AsyncMock()
    session = SimpleNamespace(begin=lambda: transaction, scalar=AsyncMock(return_value=None))
    # Isolate response validation: this test targets the transaction boundary.
    row = SimpleNamespace(**{field: None for field in action.CreateImageInterface.__fields__})
    dal = SimpleNamespace(create_image=AsyncMock(return_value=row))
    monkeypatch.setattr(action, 'ImageDal', lambda _: dal)
    monkeypatch.setattr(action, 'CreateImageInterface', lambda **kwargs: kwargs)
    monkeypatch.setattr(action, 'reserve_image_quota', AsyncMock())

    async def upload():
        dal.create_image.assert_awaited_once()
        transaction.__aexit__.assert_not_awaited()
        if fails:
            raise RuntimeError('Storage unavailable')

    coro = action.__create_image(SimpleNamespace(company_id=COMPANY, size=10,
        file_path=ROOT, file_name='test.png'), COMPANY, session, before_commit=upload)
    if fails:
        with pytest.raises(RuntimeError):
            asyncio.run(coro)
        assert transaction.__aexit__.await_args.args[0] is RuntimeError
    else:
        asyncio.run(coro)
        transaction.__aexit__.assert_awaited_once_with(None, None, None)


def test_presigned_endpoint_explicitly_tracks_new_upload(monkeypatch):
    from image import api_handlers as api
    user_id = UUID('00000000-0000-4000-8000-000000000003')
    session = object()
    request = SimpleNamespace(company_id=COMPANY, file_path=ROOT, file_name='photo.png', size=10)
    creator = AsyncMock(return_value=object())
    monkeypatch.setattr(api, '__create_image', creator)
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=SimpleNamespace(
        is_owner=True, is_admin=False, is_moderator=False)))
    monkeypatch.setattr(api, 'S3Client', lambda: SimpleNamespace(
        generate_put_presigned_url=AsyncMock(return_value='https://example.test/upload')))
    monkeypatch.setattr(api, 'CreateImageResponse', lambda **kwargs: kwargs)
    result = asyncio.run(api.create_loaded_url(request, db=session,
                                              cur_user=SimpleNamespace(user_id=user_id)))
    assert result['url'] == 'https://example.test/upload'
    assert result['required_headers'] == {'If-None-Match':'*'}
    creator.assert_awaited_once_with(request, user_id, session, pending_upload=True)
