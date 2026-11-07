"""Explicit identity linking. Similarity never grants account access."""
import secrets
import time
from datetime import timedelta
from uuid import UUID, uuid4
from typing import Optional
from pydantic import BaseModel
from pydantic import constr
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import jwt
from sqlalchemy import select, func, or_
from sqlalchemy.dialects.postgresql import insert
from db import AuthAccountDB, AuthProvider, UserDB
from db.account_link_model import AccountLinkFlowDB, AccountSuggestionDB
from db.check_model import utc_now
from db.session import get_db
from user.actions.get_current_user_from_token_action import __get_user_from_token
from user.account_status import require_confirmed
from utils.constants import EMPTY_PHONE
import settings

router = APIRouter()
PROVIDERS = {'google': AuthProvider.GOOGLE, 'yandex': AuthProvider.YANDEX, 'telegram': AuthProvider.TELEGRAM}


def enabled(provider):
    return bool(getattr(settings, provider.upper()+'_CLIENT_ID', '') and getattr(settings, provider.upper()+'_CLIENT_SECRET', ''))


@router.get('/accounts')
async def accounts(response: Response, db=Depends(get_db), actor=Depends(__get_user_from_token)):
    response.headers['Cache-Control'] = 'no-store'
    async with db.begin():
        rows = (await db.execute(select(AuthAccountDB.provider).where(AuthAccountDB.user_id == actor.user_id))).scalars().all()
        return {'providers': [{'provider': provider, 'linked': kind in rows, 'available': enabled(provider)} for provider,kind in PROVIDERS.items()]}


class StartLink(BaseModel):
    suggestion_id: Optional[UUID] = None

    class Config:
        extra = 'forbid'


@router.post('/accounts/{provider}/start')
async def start_link(provider: str, response: Response, body: StartLink = StartLink(), db=Depends(get_db), actor=Depends(__get_user_from_token)):
    if provider not in PROVIDERS or not enabled(provider):
        raise HTTPException(503, 'Provider is not configured')
    async with db.begin():
        target = None
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended('link-start:'+str(actor.user_id),0))))
        recent=await db.scalar(select(func.count()).select_from(AccountLinkFlowDB).where(
            AccountLinkFlowDB.user_id==actor.user_id,AccountLinkFlowDB.expires_at>utc_now()))
        if recent>=10:
            raise HTTPException(429,'Too many linking attempts; retry later')
        if body.suggestion_id:
            suggestion = await db.scalar(select(AccountSuggestionDB).where(AccountSuggestionDB.suggestion_id==body.suggestion_id,
                AccountSuggestionDB.status!='dismissed',or_(AccountSuggestionDB.left_id==actor.user_id,AccountSuggestionDB.right_id==actor.user_id)))
            if suggestion is None:
                raise HTTPException(404,'Suggestion not found')
            target = suggestion.right_id if suggestion.left_id==actor.user_id else suggestion.left_id
        flow = AccountLinkFlowDB(user_id=actor.user_id, provider=provider, target_user_id=target, expires_at=utc_now()+timedelta(minutes=10))
        db.add(flow)
        await db.flush()
        extra = {'link_id': str(flow.flow_id)}
    if provider == 'google':
        from auth.google_oauth import build_start
        return build_start(response, extra)
    if provider == 'telegram':
        from auth.telegram_oauth import build_start
        return build_start(response, extra)
    state = secrets.token_urlsafe(32)
    cookie = jwt.encode({'state':state,'purpose':'yandex-login','exp':int(time.time())+600,**extra},settings.SECRET_KEY,algorithm='HS256')
    response.set_cookie('culta_yandex_flow',cookie,max_age=600,httponly=True,
        secure=settings.YANDEX_REDIRECT_URI.startswith('https:'),samesite='lax',path='/login/auth/yandex')
    response.headers['Cache-Control'] = 'no-store'
    return {'url':'https://oauth.yandex.ru/authorize?'+urlencode(dict(response_type='code',client_id=settings.YANDEX_CLIENT_ID,
        redirect_uri=settings.YANDEX_REDIRECT_URI,state=state,force_confirm='yes'))}


async def link_actor(flow, request, db):
    if not flow.get('link_id'):
        return None
    authorization = request.headers.get('authorization','')
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Sign in again to finish linking')
    actor = await __get_user_from_token(authorization[7:], db)
    try:
        flow_id = UUID(flow['link_id'])
    except (ValueError, TypeError):
        raise HTTPException(400, 'Invalid link flow')
    async with db.begin():
        saved = await db.get(AccountLinkFlowDB,flow_id)
        if not saved or saved.user_id != actor.user_id or saved.consumed or saved.expires_at <= utc_now():
            raise HTTPException(400, 'Invalid or expired link flow')
    return actor


async def pair(db, first, second):
    left,right = sorted((first,second))
    await db.execute(insert(AccountSuggestionDB).values(suggestion_id=uuid4(),left_id=left,right_id=right,
        status='pending',updated_at=utc_now()).on_conflict_do_nothing(constraint='uq_account_suggestion_pair'))
    return await db.scalar(select(AccountSuggestionDB).where(AccountSuggestionDB.left_id==left,
        AccountSuggestionDB.right_id==right).with_for_update())


async def finish_link(db, flow, actor, provider, subject):
    if not isinstance(subject,str) or not subject:
        raise HTTPException(400,'Invalid provider identity')
    async with db.begin():
        saved = await db.scalar(select(AccountLinkFlowDB).where(AccountLinkFlowDB.flow_id==UUID(flow['link_id'])).with_for_update())
        if not saved or saved.user_id != actor.user_id or saved.provider != provider or saved.consumed or saved.expires_at <= utc_now():
            raise HTTPException(400,'Invalid or expired link flow')
        user = await db.scalar(select(UserDB).where(UserDB.user_id==actor.user_id).with_for_update().execution_options(populate_existing=True))
        require_confirmed(user)
        await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(provider+':'+subject,0))))
        account = await db.scalar(select(AuthAccountDB).where(AuthAccountDB.provider==PROVIDERS[provider],AuthAccountDB.provider_user_id==subject))
        saved.consumed = True
        if saved.target_user_id and (account is None or account.user_id != saved.target_user_id):
            return {'linked':False,'verification_failed':True}
        if account and account.user_id != actor.user_id:
            other=await db.get(UserDB,account.user_id)
            if other is None or not other.is_active or other.account_status!='confirmed':
                return {'linked':False,'verification_failed':True}
            suggestion = await pair(db,actor.user_id,account.user_id)
            suggestion.status = 'verified'
            suggestion.changed_by = actor.user_id
            return {'linked':False,'separate_account':True}
        if not account:
            db.add(AuthAccountDB(provider=PROVIDERS[provider],provider_user_id=subject,user_id=actor.user_id))
        return {'linked':True,'provider':provider}


@router.get('/account-suggestions')
async def suggestions(response: Response, db=Depends(get_db), actor=Depends(__get_user_from_token)):
    response.headers['Cache-Control'] = 'no-store'
    async with db.begin():
        conditions=[]
        candidates=[]
        if actor.email:
            conditions.append(func.lower(func.trim(UserDB.email))==actor.email.strip().lower())
        normalized_phone = ''.join(c for c in actor.phone or '' if c.isdigit())
        if len(normalized_phone)==11 and normalized_phone[0] in '78':
            normalized_phone=normalized_phone[1:]
        phone_valid = len(normalized_phone)>=10 and normalized_phone!=EMPTY_PHONE[-10:] and len(set(normalized_phone))>1
        if phone_valid:
            phone_digits=func.regexp_replace(UserDB.phone,'[^0-9]','','g')
            conditions.append(func.regexp_replace(phone_digits,'^[78]([0-9]{10})$',r'\1')==normalized_phone)
        name,surname = (actor.name or '').strip().lower(),(actor.surname or '').strip().lower()
        if len(name)>=2 and len(surname)>=2:
            conditions.append((func.lower(func.trim(UserDB.name))==name)&(func.lower(func.trim(UserDB.surname))==surname))
        if conditions:
            candidates = (await db.execute(select(UserDB.user_id).where(UserDB.user_id!=actor.user_id,
                UserDB.is_active.is_(True),UserDB.account_status=='confirmed',or_(*conditions)).order_by(UserDB.user_id).limit(20))).scalars().all()
            for target in candidates:
                await pair(db,actor.user_id,target)
        rows = (await db.execute(select(AccountSuggestionDB).where(
            or_(AccountSuggestionDB.left_id==actor.user_id,AccountSuggestionDB.right_id==actor.user_id),
            AccountSuggestionDB.status!='dismissed').order_by(AccountSuggestionDB.updated_at.desc()).limit(20))).scalars().all()
        # Do not expose another profile's name, phone, email, balances or privileges.
        return [{'id':row.suggestion_id,'status':row.status} for row in rows
                if row.status=='verified' or (row.right_id if row.left_id==actor.user_id else row.left_id) in candidates]


@router.post('/account-suggestions/{suggestion_id}/dismiss')
async def dismiss(suggestion_id: UUID, db=Depends(get_db), actor=Depends(__get_user_from_token)):
    async with db.begin():
        row = await db.scalar(select(AccountSuggestionDB).where(AccountSuggestionDB.suggestion_id==suggestion_id,
            or_(AccountSuggestionDB.left_id==actor.user_id,AccountSuggestionDB.right_id==actor.user_id)).with_for_update())
        if row is None:
            raise HTTPException(404,'Suggestion not found')
        row.status='dismissed'
        row.changed_by=actor.user_id
    return {'dismissed':True}


class VerifyPassword(BaseModel):
    email: constr(min_length=3,max_length=254)
    password: constr(min_length=1,max_length=1024)

    class Config:
        extra='forbid'


@router.post('/account-suggestions/{suggestion_id}/verify-password')
async def verify_password(suggestion_id: UUID, body: VerifyPassword, request: Request, db=Depends(get_db), actor=Depends(__get_user_from_token)):
    from utils.hashing import Hasher
    from auth.rate_limits import enforce_auth_limit
    await enforce_auth_limit(request, db, body.email)
    valid=False
    async with db.begin():
        row=await db.scalar(select(AccountSuggestionDB).where(AccountSuggestionDB.suggestion_id==suggestion_id,
            AccountSuggestionDB.status!='dismissed',or_(AccountSuggestionDB.left_id==actor.user_id,AccountSuggestionDB.right_id==actor.user_id)).with_for_update())
        if row is None:
            raise HTTPException(404,'Suggestion not found')
        now=utc_now()
        if row.verify_after and row.verify_after>now and row.verification_attempts>=5:
            raise HTTPException(429,'Retry after 10 minutes')
        if not row.verify_after or row.verify_after<=now:
            row.verification_attempts=0
            row.verify_after=now+timedelta(minutes=10)
        row.verification_attempts+=1
        target=await db.get(UserDB,row.right_id if row.left_id==actor.user_id else row.left_id)
        if target and target.is_active and target.account_status=='confirmed' and target.email and target.email.casefold()==body.email.strip().casefold():
            valid=await Hasher.verify_async(body.password,target.hashed_password)
        if valid:
            row.status='verified'
            row.changed_by=actor.user_id
    if not valid:
        raise HTTPException(400,'Could not confirm this suggested account')
    return {'verified':True,'merged':False}
