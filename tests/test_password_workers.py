"""Password CPU work must not block the event loop or grow an unlimited queue."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from utils.hashing import Hasher, PasswordWorkerPool


@pytest.fixture
def pool():
    worker_pool = PasswordWorkerPool(workers=1, capacity=2)
    yield worker_pool
    worker_pool.executor.shutdown(wait=True, cancel_futures=True)


def test_real_password_roundtrip():
    async def scenario():
        encoded = await Hasher.hash_async('test-password')
        assert await Hasher.verify_async('test-password', encoded)
        assert not await Hasher.verify_async('wrong-password', encoded)
    asyncio.run(scenario())


def test_work_runs_off_event_loop(pool):
    async def scenario():
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = threading.Event()
        main_thread = threading.get_ident()

        def operation():
            loop.call_soon_threadsafe(started.set)
            assert release.wait(timeout=3)
            return threading.get_ident()

        task = asyncio.create_task(pool.run(operation))
        try:
            # Only the event loop can reach this line and release the worker.
            await asyncio.wait_for(started.wait(), timeout=1)
        finally:
            release.set()
        assert await task != main_thread
    asyncio.run(scenario())


def test_capacity_is_bounded_even_when_running_request_is_cancelled(pool):
    async def scenario():
        started = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()

        def operation():
            loop.call_soon_threadsafe(started.set)
            assert release.wait(timeout=3)
            return 'finished'

        running = asyncio.create_task(pool.run(operation))
        queued = None
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
            queued = asyncio.create_task(pool.run(lambda: 'queued'))
            await asyncio.sleep(0)
            with pytest.raises(HTTPException) as error:
                await pool.run(lambda: 'overflow')
            assert error.value.status_code == 503
            assert error.value.headers == {'Retry-After': '1'}
        finally:
            release.set()
            if queued is not None:
                assert await queued == 'queued'
        assert await pool.run(lambda: 'recovered') == 'recovered'
    asyncio.run(scenario())


def test_worker_exception_releases_capacity(pool):
    def fail():
        raise ValueError('test failure')

    async def scenario():
        for _ in range(3):
            with pytest.raises(ValueError, match='test failure'):
                await pool.run(fail)
        assert await pool.run(lambda: True)
    asyncio.run(scenario())


def test_login_uses_async_verification(monkeypatch):
    from auth.actions_by_login import authenticate_user_action as login
    user = SimpleNamespace(hashed_password='hash')
    monkeypatch.setattr(login, '__get_user_by_email_for_auth', AsyncMock(return_value=user))
    verify = AsyncMock(return_value=True)
    monkeypatch.setattr(Hasher, 'verify_async', verify)
    assert asyncio.run(login.authenticate_user_by_login('test@example.com', 'password', object())) is user
    verify.assert_awaited_once_with('password', 'hash')


def test_email_confirmation_uses_async_verification(monkeypatch):
    from auth.email_confirmation import confirmed_credentials
    user = SimpleNamespace(hashed_password='hash', is_active=True, account_status='pending')
    session = SimpleNamespace(scalar=AsyncMock(return_value=user))
    verify = AsyncMock(return_value=False)
    monkeypatch.setattr(Hasher, 'verify_async', verify)
    with pytest.raises(HTTPException) as error:
        asyncio.run(confirmed_credentials(session, 'test@example.com', 'wrong'))
    assert error.value.status_code == 401
    verify.assert_awaited_once_with('wrong', 'hash')
