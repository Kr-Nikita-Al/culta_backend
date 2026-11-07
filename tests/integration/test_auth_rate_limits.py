import asyncio
from collections import Counter

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from starlette.requests import Request

from auth.rate_limits import enforce_auth_limit, bucket_key

pytestmark = pytest.mark.integration


def request(ip='192.0.2.1'):
    return Request({'type': 'http', 'client': (ip, 1234), 'headers': [
        (b'x-forwarded-for', b'198.51.100.1')]})


async def attempt(pg, email='person@example.test', ip='192.0.2.1', registration=False):
    async with pg.sessions() as db:
        try:
            await enforce_auth_limit(request(ip), db, email, registration=registration)
            return 200
        except HTTPException as error:
            assert int(error.headers['Retry-After']) > 0
            return error.status_code


def test_concurrent_account_limit_across_sessions(pg):
    async def scenario():
        results = await asyncio.gather(*(attempt(pg, ip=f'192.0.2.{i}') for i in range(30)))
        assert Counter(results) == {200: 20, 429: 10}
        assert await attempt(pg, email=' PERSON@EXAMPLE.TEST ') == 429
        assert await attempt(pg, email='another@example.test') == 200
    asyncio.run(scenario())


def test_registration_ip_limit_and_expiry(pg):
    async def scenario():
        for i in range(20):
            assert await attempt(pg, email=f'person{i}@example.test', registration=True) == 200
        assert await attempt(pg, email='new@example.test', registration=True) == 429
        async with pg.sessions() as db, db.begin():
            await db.execute(text("UPDATE auth_rate_limit SET expires_at=clock_timestamp()-interval '1 second'"))
        assert await attempt(pg, email='new@example.test', registration=True) == 200
    asyncio.run(scenario())


def test_registration_account_limit_across_ips(pg):
    async def scenario():
        results = [await attempt(pg, ip=f'192.0.2.{i}', registration=True) for i in range(6)]
        assert results == [200] * 5 + [429]
    asyncio.run(scenario())


def test_failed_logins_commit_and_share_limits_between_routes(pg):
    for i in range(20):
        if i % 2:
            response = pg.client.post('/login/session', json={'email': 'absent@example.test', 'password': 'wrong'})
        else:
            response = pg.client.post('/login/token', data={'username': 'absent@example.test', 'password': 'wrong'})
        assert response.status_code == 401, response.text
    response = pg.client.post('/login/email/request-code', json={'email': 'absent@example.test', 'password': 'wrong'})
    assert response.status_code == 429, response.text
    assert int(response.headers['retry-after']) > 0
    with pg.engine.connect() as connection:
        row = connection.execute(text('SELECT attempts FROM auth_rate_limit WHERE bucket_key=:key'),
            {'key': bucket_key('credentials', 'account', 'absent@example.test')}).scalar_one()
        assert row == 21


def test_forwarded_header_does_not_choose_ip_bucket(pg):
    asyncio.run(attempt(pg))
    with pg.engine.connect() as connection:
        keys = set(connection.execute(text('SELECT bucket_key FROM auth_rate_limit')).scalars())
    assert bucket_key('credentials', 'ip', '192.0.2.1') in keys
    assert bucket_key('credentials', 'ip', '198.51.100.1') not in keys
