"""Credential-bound confirmation. Delivery is disabled unless explicitly local."""
import hashlib
import asyncio
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from db import UserDB
from utils.hashing import Hasher
import settings


def code_hash(user, code):
    payload = f'email-confirmation:{user.user_id}:{user.email}:{code}'.encode()
    return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()


def deliver_local(email, code):
    # Explicit opt-in; ENV alone must never turn on a secret-bearing sink.
    if settings.ENV not in ('local', 'development', 'dev', 'test') or os.environ.get('EMAIL_DELIVERY_MODE') != 'local':
        raise HTTPException(503, 'Email delivery is not configured')
    directory = Path(os.environ.get('EMAIL_LOCAL_OUTBOX', '.local-email-outbox')).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    path = directory / f'{uuid4()}.json'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump({'to': email, 'code': code, 'expires_in_seconds': 600}, output)


async def confirmed_credentials(session, email, password):
    user = await session.scalar(select(UserDB).where(UserDB.email == email).with_for_update(of=UserDB))
    if user is None or not await Hasher.verify_async(password, user.hashed_password):
        raise HTTPException(401, 'Incorrect username or password')
    if not user.is_active or user.account_status in ('blocked', 'deleted'):
        raise HTTPException(403, 'Account unavailable')
    return user


async def send_code(session, email, password):
    async with session.begin():
        user = await confirmed_credentials(session, email, password)
        if user.account_status == 'confirmed':
            return {'status': 'confirmed'}
        now = datetime.now(timezone.utc)
        if user.email_code_sent_at and now < user.email_code_sent_at + timedelta(seconds=60):
            raise HTTPException(429, 'Retry after 60 seconds', headers={'Retry-After': '60'})
        code = f'{secrets.randbelow(1000000):06d}'
        mode = os.environ.get('EMAIL_DELIVERY_MODE', 'smtp')
        if mode == 'local':
            await asyncio.to_thread(deliver_local, user.email, code)
        elif mode == 'smtp':
            from auth.smtp_delivery import deliver_smtp
            await asyncio.to_thread(deliver_smtp, user.email, code)
        else:
            raise HTTPException(503, 'Email delivery is not configured')
        user.email_code_hash = code_hash(user, code)
        user.email_code_expires = now + timedelta(minutes=10)
        user.email_code_sent_at = now
        user.email_code_attempts = 0
    return {'status': 'sent', 'expires_in': 600, 'retry_after': 60}


async def verify_code(session, email, password, code):
    invalid = False
    async with session.begin():
        user = await confirmed_credentials(session, email, password)
        if (not user.email_code_hash or user.email_code_attempts >= 5 or
                not user.email_code_expires or user.email_code_expires <= datetime.now(timezone.utc)):
            raise HTTPException(400, 'Code is invalid or expired')
        user.email_code_attempts += 1
        if not hmac.compare_digest(user.email_code_hash, code_hash(user, code)):
            invalid = True
            if user.email_code_attempts >= 5:
                user.email_code_hash = None
        else:
            user.account_status = 'confirmed'
            user.email_code_hash = None
            user.email_code_expires = None
    # Raise after commit, otherwise unsuccessful attempts would roll back.
    if invalid:
        raise HTTPException(400, 'Code is invalid or expired')
    return {'status': 'confirmed'}


async def confirm_yandex_user(session, user_id):
    async with session.begin():
        user = await session.scalar(select(UserDB).where(UserDB.user_id == user_id).with_for_update(of=UserDB))
        if user is None or not user.is_active or user.account_status in ('blocked', 'deleted'):
            raise HTTPException(403, 'Account unavailable')
        user.account_status = 'confirmed'
        user.email_code_hash = None
        user.email_code_expires = None
        return user
