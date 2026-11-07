"""Shared PostgreSQL limits, committed before credential checks or registration."""
import hashlib
import hmac
import math

from fastapi import HTTPException, Request
from sqlalchemy import text
import settings


def bucket_key(scope, kind, value):
    # No raw email/IP addresses in the rate-limit table or SQL parameters.
    return hmac.new(settings.SECRET_KEY.encode(),
                    f'auth-limit:{scope}:{kind}:{value}'.encode(), hashlib.sha256).hexdigest()


CONSUME = text('''
    INSERT INTO auth_rate_limit (bucket_key, attempts, expires_at)
    VALUES (:key, 1, clock_timestamp() + :seconds * interval '1 second')
    ON CONFLICT (bucket_key) DO UPDATE SET
      attempts = CASE WHEN auth_rate_limit.expires_at <= clock_timestamp() THEN 1
                      ELSE LEAST(auth_rate_limit.attempts + 1, :maximum + 1) END,
      expires_at = CASE WHEN auth_rate_limit.expires_at <= clock_timestamp()
                       THEN clock_timestamp() + :seconds * interval '1 second'
                       ELSE auth_rate_limit.expires_at END
    RETURNING attempts, EXTRACT(EPOCH FROM (expires_at - clock_timestamp())) AS remaining
''')


async def enforce_auth_limit(request: Request, db, identifier: str, *, registration=False):
    scope = 'registration' if registration else 'credentials'
    seconds, ip_max, account_max = (3600, 20, 5) if registration else (600, 100, 20)
    # Uvicorn must trust only the real reverse proxy. Never read forwarded headers here.
    address = request.client.host if request.client else 'unknown'
    buckets = [('ip', address, ip_max), ('account', identifier.strip().casefold(), account_max)]
    retry = None
    async with db.begin():
        # Bounded cleanup; skip rows currently used by another request.
        await db.execute(text('''DELETE FROM auth_rate_limit WHERE bucket_key IN
            (SELECT bucket_key FROM auth_rate_limit WHERE expires_at <= clock_timestamp()
             ORDER BY expires_at LIMIT 50 FOR UPDATE SKIP LOCKED)'''))
        for kind, value, maximum in buckets:
            row = (await db.execute(CONSUME, dict(key=bucket_key(scope, kind, value),
                seconds=seconds, maximum=maximum))).one()
            if row.attempts > maximum:
                retry = max(1, math.ceil(row.remaining))
                break  # A blocked IP cannot create unlimited account buckets.
    # Raise outside the transaction: rejected credentials must still consume attempts.
    if retry is not None:
        raise HTTPException(429, 'Too many attempts. Please try again later.',
                            headers={'Retry-After': str(retry)})
