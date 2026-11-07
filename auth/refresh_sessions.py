"""Opt-in refresh sessions. Tokens are bearer secrets; only hashes are stored."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from auth.rate_limits import enforce_auth_limit
from pydantic import BaseModel, constr
from sqlalchemy import select, func
from sqlalchemy.orm import noload
from db import RefreshSessionDB, UserDB
from db.session import get_db
from auth.model_dal import create_access_token
from auth.actions_by_login.authenticate_user_action import authenticate_user_by_login
from user.account_status import require_confirmed

router = APIRouter()


class Credentials(BaseModel):
    email: constr(min_length=1, max_length=254)
    password: constr(min_length=1, max_length=1024)


class RefreshBody(BaseModel):
    refresh_token: constr(min_length=1, max_length=200)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(sid):
    return str(sid) + '.' + secrets.token_urlsafe(48)


def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'


def result(user, token, expires):
    sid = token.split('.')[0]
    return {'access_token':create_access_token({'sub':user.email or str(user.user_id), 'uid':str(user.user_id), 'sid':sid}, expires_delta=timedelta(minutes=15)), 'token_type':'bearer',
            'user_id':user.user_id, 'refresh_token':token, 'refresh_expires_at':expires}


@router.post('/session')
async def start_session(body: Credentials, response: Response, request: Request, db=Depends(get_db)):
    no_cache(response)
    await enforce_auth_limit(request, db, body.email)
    user = await authenticate_user_by_login(body.email, body.password, db)
    if user is None:
        raise HTTPException(401, 'Incorrect username or password')
    require_confirmed(user)
    return await issue_session(db, user)


async def issue_session(db, user):
    require_confirmed(user)
    sid = uuid4()
    token = new_token(sid)
    async with db.begin():
        now = await db.scalar(select(func.clock_timestamp()))
        expires = now + timedelta(days=30)
        db.add(RefreshSessionDB(session_id=sid, user_id=user.user_id, token_hash=digest(token),
                                credential_hash=digest(user.hashed_password),
                                used_hashes=[], expires_at=expires, revoked=False))
    return result(user, token, expires)


async def rotate(body, db, logout=False):
    try:
        sid = UUID(body.refresh_token.split('.')[0])
    except ValueError:
        raise HTTPException(401, 'Invalid refresh token')
    failure = False
    async with db.begin():
        session = await db.scalar(select(RefreshSessionDB).where(RefreshSessionDB.session_id==sid).with_for_update())
        supplied = digest(body.refresh_token)
        now = await db.scalar(select(func.clock_timestamp()))
        if session is None:
            failure = True
        elif supplied in session.used_hashes:
            session.revoked = True  # Replay invalidates the whole refresh session.
            failure = True
        elif not hmac.compare_digest(supplied, session.token_hash):
            failure = True  # A guessed secret must not revoke somebody else's session.
        elif session.revoked or session.expires_at <= now:
            failure = True
        elif logout:
            session.revoked = True
        else:
            user = await db.scalar(select(UserDB).options(noload('*')).where(UserDB.user_id==session.user_id))
            if (user is None or not user.is_active or user.account_status != 'confirmed'
                    or digest(user.hashed_password) != session.credential_hash or len(session.used_hashes)>=500):
                session.revoked = True
                failure = True
            else:
                token = new_token(sid)
                session.used_hashes = [*session.used_hashes, session.token_hash]
                session.token_hash = digest(token)
                output = result(user, token, session.expires_at)
    # Raise only after commit so replay/blocked-account revocation is persisted.
    if failure:
        raise HTTPException(401, 'Invalid refresh token')
    return {'revoked':True} if logout else output


@router.post('/refresh')
async def refresh(body: RefreshBody, response: Response, db=Depends(get_db)):
    no_cache(response)
    return await rotate(body, db)


@router.post('/logout')
async def logout(body: RefreshBody, response: Response, db=Depends(get_db)):
    no_cache(response)
    return await rotate(body, db, logout=True)


from user.actions.get_current_user_from_token_action import __get_user_from_token


@router.get('/sessions')
async def list_sessions(response: Response, user=Depends(__get_user_from_token), db=Depends(get_db)):
    no_cache(response)
    async with db.begin():
        rows = (await db.execute(select(RefreshSessionDB.session_id, RefreshSessionDB.expires_at).where(
            RefreshSessionDB.user_id==user.user_id, RefreshSessionDB.revoked.is_(False),
            RefreshSessionDB.expires_at>func.clock_timestamp(),
            RefreshSessionDB.credential_hash==digest(user.hashed_password)))).all()
    return [{'session_id':row.session_id,'expires_at':row.expires_at} for row in rows]


@router.delete('/sessions/{session_id}')
async def revoke_session(session_id: UUID, user=Depends(__get_user_from_token), db=Depends(get_db)):
    async with db.begin():
        session = await db.scalar(select(RefreshSessionDB).where(
            RefreshSessionDB.session_id==session_id, RefreshSessionDB.user_id==user.user_id).with_for_update())
        if session is None:
            raise HTTPException(404, 'Session not found')
        session.revoked = True
    return {'revoked':True}
