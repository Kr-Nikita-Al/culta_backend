import time
import pytest
from jose import jwt
from sqlalchemy import text
import settings
pytestmark = pytest.mark.integration


def test_token_status_and_rejections(pg):
    expiry = int(time.time()) + 600
    def check(claims=None, secret=None):
        token = jwt.encode(claims if claims is not None else {'sub':'admin_a@example.test','exp':expiry},
                           secret or settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return pg.client.get('/login/token/status',headers={'Authorization':'Bearer '+token})
    result = check()
    assert result.status_code == 200, result.text
    assert result.json()['valid'] is True
    assert result.json()['user_id'] == str(pg.ids['admin_a'])
    assert 590 <= result.json()['expires_in'] <= 600
    assert result.headers['cache-control'] == 'no-store'
    assert pg.client.get('/login/token/status').status_code == 401
    assert check(secret='incorrect-secret').status_code == 401
    assert check({'sub':'admin_a@example.test','exp':int(time.time())-10}).status_code == 401
    assert check({'sub':'admin_a@example.test'}).status_code == 401
    assert check({'sub':'missing@example.test','exp':expiry}).status_code == 401
    for state in ('pending','blocked','deleted'):
        with pg.engine.begin() as conn:
            conn.execute(text('UPDATE "user" SET account_status=:state WHERE user_id=:id'),
                         {'state':state,'id':pg.ids['admin_a']})
        assert check().status_code == 403
