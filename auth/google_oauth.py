import logging
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode
import httpx
from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, constr
from sqlalchemy import select, func
from db import AuthAccountDB, AuthProvider, UserDB, UserRoleDB
from db.session import get_db
from user.model_dal import UserDAL
from user.account_status import require_confirmed
from utils.hashing import Hasher
from utils.constants import EMPTY_PHONE, EMPTY_UUID, PortalRole
from user_role.model_dal import UserRoleDAL
from auth.refresh_sessions import issue_session, no_cache
import settings

router=APIRouter()
logger=logging.getLogger(__name__)
COOKIE='culta_google_flow'
PATH='/login/auth/google'


def configured():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503,'Google login is not configured')


def build_start(response: Response, extra=None):
    configured()
    state,nonce,verifier=(secrets.token_urlsafe(32) for _ in range(3))
    cookie=jwt.encode({'state':state,'nonce':nonce,'verifier':verifier,'exp':int(time.time())+600,'purpose':'google-login',**(extra or {})},settings.SECRET_KEY,algorithm='HS256')
    response.set_cookie(COOKIE,cookie,max_age=600,httponly=True,secure=settings.GOOGLE_REDIRECT_URI.startswith('https:'),samesite='lax',path=PATH)
    no_cache(response)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(dict(client_id=settings.GOOGLE_CLIENT_ID,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,response_type='code',scope='openid email profile',state=state,
        nonce=nonce,code_challenge=challenge,code_challenge_method='S256'))}


@router.post('/start')
async def start(response: Response):
    return build_start(response)


class Callback(BaseModel):
    code: constr(min_length=1,max_length=4096)
    state: constr(min_length=1,max_length=200)


@router.post('/callback')
async def callback(body: Callback, request: Request, response: Response, db=Depends(get_db)):
    configured()
    try:
        flow=jwt.decode(request.cookies.get(COOKIE,''),settings.SECRET_KEY,algorithms=['HS256'],options={'require_exp':True})
        if flow.get('purpose')!='google-login' or not secrets.compare_digest(flow.get('state',''),body.state):
            raise ValueError()
    except (JWTError,ValueError,TypeError):
        logger.warning('Google OAuth: invalid flow cookie/state (cookie present: %s)', bool(request.cookies.get(COOKIE)))
        raise HTTPException(400,'Invalid or expired Google login state')
    response.delete_cookie(COOKIE,path=PATH)
    no_cache(response)
    from auth.account_links import link_actor, finish_link
    actor = await link_actor(flow, request, db)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            tokens=await client.post('https://oauth2.googleapis.com/token',data=dict(code=body.code,client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,redirect_uri=settings.GOOGLE_REDIRECT_URI,grant_type='authorization_code',code_verifier=flow['verifier']))
            if tokens.status_code!=200:
                logger.warning('Google OAuth: token endpoint rejected exchange (HTTP %s)', tokens.status_code)
                raise HTTPException(400,'Google authorization code rejected')
            keys=await client.get('https://www.googleapis.com/oauth2/v3/certs')
            keys.raise_for_status()
            token_data=tokens.json()
            identity=jwt.decode(token_data['id_token'],keys.json(),algorithms=['RS256'],audience=settings.GOOGLE_CLIENT_ID,
                access_token=token_data.get('access_token'),
                options={'require_exp':True,'require_sub':True,'require_aud':True,'require_iss':True})
            if identity.get('iss') not in ('https://accounts.google.com','accounts.google.com') or identity.get('nonce')!=flow['nonce'] or identity.get('email_verified') is not True:
                raise ValueError()
            email=identity['email'].strip().lower()
            subject=identity['sub']
            if not email or not isinstance(subject,str) or not subject:
                raise ValueError()
    except HTTPException:
        raise
    except (httpx.HTTPError,JWTError,KeyError,ValueError,TypeError,AttributeError) as exc:
        logger.warning('Google OAuth: identity verification failed (%s)', type(exc).__name__)
        raise HTTPException(400,'Could not verify Google identity')
    if actor is not None:
        return await finish_link(db, flow, actor, 'google', subject)
    password_hash=await Hasher.hash_async(secrets.token_urlsafe(48))
    async with db.begin():
        # Serialize Google login attempts for an identity without exposing its ID.
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended('google:'+subject,0))))
        account=await db.scalar(select(AuthAccountDB).where(AuthAccountDB.provider==AuthProvider.GOOGLE,AuthAccountDB.provider_user_id==subject))
        if account:
            user=await db.scalar(select(UserDB).where(UserDB.user_id==account.user_id))
            if user is None:
                raise HTTPException(403,'Account unavailable')
            require_confirmed(user)
        else:
            existing=await db.scalar(select(UserDB.user_id).where(func.lower(UserDB.email)==email))
            if existing:
                raise HTTPException(409,'An account with this email already exists. Sign in using its original method; automatic linking is disabled.')
            user=await UserDAL(db).create_user(name=str(identity.get('given_name',''))[:35],surname=str(identity.get('family_name',''))[:35],phone=EMPTY_PHONE,email=email,hashed_password=password_hash)
            user.account_status='confirmed'
            db.add(AuthAccountDB(provider=AuthProvider.GOOGLE,provider_user_id=subject,user_id=user.user_id))
            db.add(UserRoleDB(user_id=user.user_id,company_id=EMPTY_UUID,role='PORTAL_ROLE_USER'))
            # Only a verified first registration can bootstrap the configured role.
            if email in {value.strip().casefold() for value in settings.ACCESS_SUPER_ADMINS}:
                await UserRoleDAL(db).grant_user_role(user.user_id, EMPTY_UUID,
                    PortalRole.PORTAL_ROLE_SUPER_ADMIN, user.user_id)
    return await issue_session(db,user)
