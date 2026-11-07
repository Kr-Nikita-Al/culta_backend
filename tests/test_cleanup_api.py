import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from image import api_handlers as api
from image import move_cleanup


@pytest.mark.parametrize('admin', [False, True])
def test_explicit_cleanup_requires_owner_or_admin(monkeypatch, admin):
    role = SimpleNamespace(is_owner=False, is_admin=admin, is_moderator=True)
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=role))
    clean = AsyncMock(return_value={'deleted':0})
    monkeypatch.setattr(move_cleanup, 'cleanup_move', clean)
    monkeypatch.setattr(api, 'S3Client', lambda: object())
    call = api.cleanup_move(uuid4(), uuid4(), db=object(), cur_user=SimpleNamespace(user_id=uuid4()))
    if admin:
        assert asyncio.run(call) == {'deleted':0}
        clean.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as error: asyncio.run(call)
        assert error.value.status_code == 403
        clean.assert_not_awaited()


def test_cleanup_failure_is_not_a_move_failure(monkeypatch):
    monkeypatch.setattr(move_cleanup, 'cleanup_move', AsyncMock(side_effect=RuntimeError('DB unavailable')))
    result = asyncio.run(move_cleanup.try_cleanup_move(object(), uuid4(), uuid4()))
    assert result == {'unavailable':True}
