import httpx
import secrets
import time
from urllib.parse import urlencode
from jose import jwt, JWTError
import settings
from datetime import timedelta

from fastapi import APIRouter, Response, Request
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from auth.actions_by_yandex import __get_or_create_auth_user
from auth.model_dal import create_access_token
from db.auth_account_model import AuthProvider
from settings import YANDEX_CLIENT_ID, YANDEX_REDIRECT_URI, YANDEX_CLIENT_SECRET, ACCESS_TOKEN_EXPIRE_MINUTES
from auth.actions_by_login.authenticate_user_action import authenticate_user_by_login
from utils.constants import EMPTY_PHONE
from utils.schemas import Token
from db.session import get_db
from auth.rate_limits import enforce_auth_limit

login_router = APIRouter()
from auth.telegram_oauth import router as telegram_router
login_router.include_router(telegram_router,prefix='/auth/telegram')
from auth.google_oauth import router as google_router
login_router.include_router(google_router,prefix='/auth/google')
from auth.refresh_sessions import router as refresh_router
login_router.include_router(refresh_router)
from auth.token_status import token_status, TokenStatus
login_router.add_api_route('/token/status', token_status, methods=['GET'], response_model=TokenStatus)
from auth.password_change import PasswordChangeRequest, PasswordChangeConfirm, request_change, confirm_change

@login_router.post('/password/request-code')
async def request_password_code(body: PasswordChangeRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, db, body.identifier)
    return await request_change(db, body)

@login_router.post('/password/confirm')
async def confirm_password_code(body: PasswordChangeConfirm, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, db, body.identifier)
    return await confirm_change(db, body)

from pydantic import BaseModel, constr
from auth.email_confirmation import send_code, verify_code


class EmailCredentials(BaseModel):
    # Match login semantics, including existing/internal account email addresses.
    email: constr(min_length=1, max_length=254)
    password: constr(min_length=1, max_length=1024)


class EmailConfirmation(EmailCredentials):
    code: constr(regex=r'^\d{6}$')


@login_router.post('/email/request-code')
async def request_email_code(body: EmailCredentials, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, db, body.email)
    return await send_code(db, str(body.email), body.password)


@login_router.post('/email/confirm')
async def confirm_email_code(body: EmailConfirmation, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_auth_limit(request, db, body.email)
    return await verify_code(db, str(body.email), body.password, body.code)


@login_router.post("/token", response_model=Token)
async def login_for_access_token(
        request: Request,
        form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    await enforce_auth_limit(request, db, form_data.username)
    user = await authenticate_user_by_login(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    from user.account_status import require_confirmed
    require_confirmed(user)
    access_token = create_access_token(data={"sub":user.email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token":access_token,"token_type":"bearer","user_id":user.user_id}


@login_router.get("/auth/yandex")
async def auth_yandex():
    state=secrets.token_urlsafe(32)
    response=RedirectResponse('https://oauth.yandex.ru/authorize?'+urlencode(dict(
        response_type='code',client_id=YANDEX_CLIENT_ID,redirect_uri=YANDEX_REDIRECT_URI,state=state)))
    flow=jwt.encode({'state':state,'purpose':'yandex-login','exp':int(time.time())+600},settings.SECRET_KEY,algorithm='HS256')
    response.set_cookie('culta_yandex_flow',flow,max_age=600,httponly=True,
        secure=YANDEX_REDIRECT_URI.startswith('https:'),samesite='lax',path='/login/auth/yandex')
    response.headers['Cache-Control']='no-store'
    return response


@login_router.get("/auth/yandex/callback")
async def auth_yandex_callback(
        response: Response,
        request: Request,
        code: str = None,
        error: str = None,
        state: str = None,
        db: AsyncSession = Depends(get_db)
):
    # Passwords and authorization codes alone do not bind a login to this browser.
    try:
        flow=jwt.decode(request.cookies.get('culta_yandex_flow',''),settings.SECRET_KEY,algorithms=['HS256'],options={'require_exp':True})
        if not state or flow.get('purpose')!='yandex-login' or not secrets.compare_digest(flow.get('state',''),state):
            raise ValueError()
    except (JWTError,ValueError,TypeError):
        raise HTTPException(400,'Invalid or expired Yandex login state')
    response.delete_cookie('culta_yandex_flow',path='/login/auth/yandex')
    response.headers['Cache-Control']='no-store'
    from auth.account_links import link_actor, finish_link
    actor = await link_actor(flow, request, db)
    # Обработка ошибок
    if error or not code:
        raise HTTPException(400, "Authorization failed")

    # Обмен кода на токен
    token_url = "https://oauth.yandex.ru/token"
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": YANDEX_CLIENT_ID,
                "client_secret": YANDEX_CLIENT_SECRET
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if token_response.status_code != 200:
            raise HTTPException(400, "Token exchange failed")

        token_data = token_response.json()
        access_token = token_data["access_token"]

    # Получение данных пользователя
    user_info_url = "https://login.yandex.ru/info?format=json"
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            user_info_url,
            headers={"Authorization": f"OAuth {access_token}"}
        )

        if user_response.status_code != 200:
            raise HTTPException(400, "Failed to fetch user static_data")

        user_data = user_response.json()

    # Обработка данных пользователя
    email = user_data.get("default_email", "")
    name = f"{user_data.get('first_name', '')}"
    surname = f"{user_data.get('last_name', '')}"
    phone_data = user_data.get('default_phone')
    phone = phone_data.get('number') if isinstance(phone_data, dict) else None
    phone = phone if isinstance(phone, str) and phone else EMPTY_PHONE

    if actor is not None:
        return await finish_link(db, flow, actor, 'yandex', user_data.get('id'))
    # Создание пользователя; совпадение email не разрешает привязку.
    user = await __get_or_create_auth_user(
        db,
        provider=AuthProvider.YANDEX,  # Передаем Enum значение
        provider_user_id=user_data["id"],
        email=email,
        name=name,
        surname=surname,
        phone=phone
    )
    from auth.email_confirmation import confirm_yandex_user
    user = await confirm_yandex_user(db, user.user_id)
    from auth.refresh_sessions import issue_session, no_cache
    no_cache(response)
    return await issue_session(db, user)


from auth.account_links import router as account_links_router
login_router.include_router(account_links_router)
