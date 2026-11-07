import asyncio
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from pydantic import BaseModel, constr, validator
from auth.email_confirmation import confirmed_credentials, deliver_local
from auth.smtp_delivery import deliver_smtp
from utils.hashing import Hasher
import settings

class PasswordChangeRequest(BaseModel):
    identifier: constr(strip_whitespace=True, min_length=1, max_length=254)
    old_password: constr(min_length=1, max_length=72)
    new_password: constr(min_length=8, max_length=72)

    @validator('old_password', 'new_password')
    def bcrypt_limit(cls, value):
        if len(value.encode()) > 72:
            raise ValueError('Password exceeds 72 bytes')
        return value

class PasswordChangeConfirm(PasswordChangeRequest):
    code: constr(regex=r'^\d{6}$')

def email_identifier(value):
    if re.fullmatch(r'(?:\+7|8)\d{10}', re.sub(r'[\s()-]', '', value)):
        raise HTTPException(422, 'Telegram delivery is not available')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise HTTPException(422, 'Invalid email or phone')
    return value

def digest(user, code, new_password):
    payload=f'password-change:{user.user_id}:{user.hashed_password}:{new_password}:{code}'
    return hmac.new(settings.SECRET_KEY.encode(),payload.encode(),hashlib.sha256).hexdigest()

async def request_change(db, body):
    email=email_identifier(body.identifier)
    async with db.begin():
        user=await confirmed_credentials(db,email,body.old_password)
        if user.account_status!='confirmed':raise HTTPException(403,'Email confirmation required')
        if body.old_password==body.new_password:raise HTTPException(422,'New password must differ')
        now=datetime.now(timezone.utc)
        if user.password_code_sent_at and now<user.password_code_sent_at+timedelta(seconds=60):
            raise HTTPException(429,'Retry after 60 seconds')
        code=f'{secrets.randbelow(1000000):06d}'
        mode=os.environ.get('EMAIL_DELIVERY_MODE','smtp')
        if mode=='local':await asyncio.to_thread(deliver_local,email,code)
        elif mode=='smtp':await asyncio.to_thread(deliver_smtp,email,code,'смены пароля')
        else:raise HTTPException(503,'Email delivery unavailable')
        user.password_code_hash=digest(user,code,body.new_password)
        user.password_code_expires=now+timedelta(minutes=10)
        user.password_code_sent_at=now
        user.password_code_attempts=0
    return {'status':'sent','retry_after':60}

async def confirm_change(db, body):
    email=email_identifier(body.identifier)
    invalid=False
    async with db.begin():
        user=await confirmed_credentials(db,email,body.old_password)
        if user.account_status!='confirmed':raise HTTPException(403,'Account unavailable')
        if not user.password_code_hash or user.password_code_attempts>=5 or not user.password_code_expires or user.password_code_expires<=datetime.now(timezone.utc):
            raise HTTPException(400,'Invalid or expired code')
        user.password_code_attempts+=1
        if not hmac.compare_digest(user.password_code_hash,digest(user,body.code,body.new_password)):
            invalid=True
            if user.password_code_attempts>=5:user.password_code_hash=None
        else:
            user.hashed_password=await Hasher.hash_async(body.new_password)
            user.password_code_hash=None;user.password_code_expires=None
            user.email_code_hash=None;user.email_code_expires=None
    if invalid:raise HTTPException(400,'Invalid or expired code')
    return {'status':'changed'}
