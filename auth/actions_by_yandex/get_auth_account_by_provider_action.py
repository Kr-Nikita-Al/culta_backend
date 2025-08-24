from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model_dal import AuthDal
from db import AuthAccountDB, AuthProvider


async def __get_auth_account_by_provider(provider_user_id: str, provider: AuthProvider, session: AsyncSession) -> \
        Union[AuthAccountDB, None]:
    async with session.begin():
        auth_dal = AuthDal(session)
        auth_account = await auth_dal.get_auth_account_by_provider(
            provider_user_id=provider_user_id,
            provider=provider
        )
        return auth_account
