from datetime import datetime
from datetime import timedelta
from sqlalchemy import select, update, and_
from typing import Optional, Union
from jose import jwt
from uuid import UUID

from db import AuthAccountDB, AuthProvider
from settings import SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM
from sqlalchemy.ext.asyncio import AsyncSession


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


class AuthDal:

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_auth_account(self, provider: AuthProvider, provider_user_id: str, user_id: UUID) -> AuthAccountDB:
        new_auth_account = AuthAccountDB(
            provider=provider,
            provider_user_id=provider_user_id,
            user_id=user_id
        )
        self.db_session.add(new_auth_account)
        await self.db_session.flush()
        return new_auth_account

    async def get_auth_account_by_auth_id(self, auth_id: UUID) -> Union[AuthAccountDB, None]:
        query = select(AuthAccountDB).where(AuthAccountDB.auth_id == auth_id)
        res = await self.db_session.execute(query)
        auth_account_row = res.unique().fetchone()
        if auth_account_row is not None:
            return auth_account_row[0]
        return None

    async def get_auth_account_by_provider(self,
                                           provider_user_id: str,
                                           provider: AuthProvider
                                           ) -> Union[AuthAccountDB, None]:
        query = select(AuthAccountDB).where(and_(AuthAccountDB.provider_user_id == provider_user_id,
                                                 AuthAccountDB.provider == provider))
        res = await self.db_session.execute(query)
        auth_account_row = res.unique().fetchone()
        if auth_account_row is not None:
            return auth_account_row[0]
        return None

    async def get_auth_account_by_user_id(self, user_id: UUID, provider: AuthProvider) -> Union[AuthAccountDB, None]:
        query = select(AuthAccountDB).where(and_(AuthAccountDB.user_id == user_id,
                                                 AuthAccountDB.provider == provider))
        res = await self.db_session.execute(query)
        auth_account_row = res.unique().fetchone()
        if auth_account_row is not None:
            return auth_account_row[0]
        return None

    # async def update_company(self, company_id: UUID, **kwargs) -> Union[UUID, None]:
    #     query = update(CompanyDB).where(and_(CompanyDB.company_id == company_id,
    #                                          CompanyDB.is_active == True)) \
    #         .values(kwargs) \
    #         .returning(CompanyDB.company_id)
    #     res = await self.db_session.execute(query)
    #     update_company_id_row = res.unique().fetchone()
    #     if update_company_id_row is not None:
    #         return update_company_id_row[0]
    #     return None

