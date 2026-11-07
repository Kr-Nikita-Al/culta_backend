from datetime import datetime, timedelta, timezone
from jose import jwt
from auth.model_dal import create_access_token
from settings import ACCESS_TOKEN_EXPIRE_MINUTES


def test_explicit_zero_lifetime_does_not_use_default():
    before = int(datetime.now(timezone.utc).timestamp())
    claims = jwt.get_unverified_claims(create_access_token({'sub': 'test'}, timedelta(0)))
    after = int(datetime.now(timezone.utc).timestamp())
    assert before <= claims['exp'] <= after


def test_default_lifetime_is_preserved():
    before = int(datetime.now(timezone.utc).timestamp())
    claims = jwt.get_unverified_claims(create_access_token({'sub': 'test'}))
    after = int(datetime.now(timezone.utc).timestamp())
    lifetime = int(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds())
    assert before + lifetime <= claims['exp'] <= after + lifetime
