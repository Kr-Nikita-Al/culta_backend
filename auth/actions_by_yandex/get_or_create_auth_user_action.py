from random import choice
from string import ascii_lowercase, digits, ascii_uppercase
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from auth.actions_by_yandex.get_auth_account_by_provider_action import __get_auth_account_by_provider
from auth.actions_by_yandex.get_auth_account_by_user_id_action import __get_auth_account_by_user_id
from auth.actions_by_yandex.create_auth_account_action import __create_auth_account
from auth.interface_request import CreateAuthAccountRequest
from db import UserDB, AuthProvider
from user.actions import __get_user_by_email_for_auth, __create_user
from user.interface_request import CreateUserRequest
from user_role.actions import __grant_user_role
from user_role.interface_request import GrantUserRoleRequest
from utils.constants import PortalRole


async def __get_or_create_auth_user(
        db: AsyncSession,
        provider: AuthProvider,
        provider_user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        surname: Optional[str] = None,
        phone: Optional[str] = None,
) -> UserDB:
    # Поиск существующей привязки
    auth_account = await __get_auth_account_by_provider(provider_user_id=provider_user_id,
                                                        provider=provider, session=db)
    if auth_account:
        return auth_account.user
    # Поиск пользователя по email
    user = None
    if email:
        user = await __get_user_by_email_for_auth(email=email, session=db)
    # Создание нового пользователя если не найден
    if not user:
        random_password = [choice(ascii_lowercase +digits if i != 5 else ascii_uppercase) for i in range(25)]
        user_body = CreateUserRequest(name=name, surname=surname, email=email,
                                      password=''.join(random_password), phone=phone)
        user = await __create_user(user_body=user_body, session=db)
        _ = await __grant_user_role(GrantUserRoleRequest(user_id=user.user_id,
                                                         role=PortalRole.PORTAL_ROLE_USER,
                                                         creator_id=user.user_id), db)
    # Проверяем, нет ли уже привязки этого провайдера
    existing_account = await __get_auth_account_by_user_id(user_id=user.user_id, provider=provider, session=db)
    if not existing_account:
        # Создаем новую привязку
        body = CreateAuthAccountRequest(provider=provider, provider_user_id=provider_user_id, user_id=user.user_id)
        _ = await __create_auth_account(body, db)

    return user
