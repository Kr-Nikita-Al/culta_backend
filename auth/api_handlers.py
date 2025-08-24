import httpx
from datetime import timedelta

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from auth.actions_by_yandex import __get_or_create_auth_user
from auth.model_dal import AuthDal
from db.auth_account_model import AuthProvider
from settings import YANDEX_CLIENT_ID, YANDEX_REDIRECT_URI, YANDEX_CLIENT_SECRET, ACCESS_TOKEN_EXPIRE_MINUTES
from auth.actions_by_login.authenticate_user_action import authenticate_user_by_login
from utils.constants import EMPTY_PHONE
from utils.schemas import Token
from db.session import get_db

login_router = APIRouter()


@login_router.post("/token", response_model=Token)
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    auth_dal = AuthDal(db_session=db)
    user = await authenticate_user_by_login(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = auth_dal.create_access_token(
        data={"sub": user.email, "other_custom_data": [1, 2, 3, 4]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token,
            "token_type": "bearer",
            "user_id": user.user_id}


@login_router.get("/auth/yandex")
async def auth_yandex():
    return RedirectResponse(
        "https://oauth.yandex.ru/authorize?"
        f"response_type=code&"
        f"client_id={YANDEX_CLIENT_ID}&"
        f"redirect_uri={YANDEX_REDIRECT_URI}"
    )


@login_router.get("/auth/yandex/callback")
async def auth_yandex_callback(
        code: str | None = None,
        error: str | None = None,
        db: AsyncSession = Depends(get_db)
):
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
            raise HTTPException(400, "Failed to fetch user data")

        user_data = user_response.json()

    # Обработка данных пользователя
    email = user_data.get("default_email", "")
    name = f"{user_data.get('first_name', '')}"
    surname = f"{user_data.get('last_name', '')}"
    phone = f"{user_data.get('default_phone', EMPTY_PHONE).get('number', EMPTY_PHONE)}"

    # Создание/объединение пользователя
    user = await __get_or_create_auth_user(
        db,
        provider=AuthProvider.YANDEX,  # Передаем Enum значение
        provider_user_id=user_data["id"],
        email=email,
        name=name,
        surname=surname,
        phone=phone
    )
    auth_dal = AuthDal()
    access_token = auth_dal.create_access_token(
        data={"sub": email, "other_custom_data": [1, 2, 3, 4]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token,
            "token_type": "bearer",
            "user_id": user.user_id}

