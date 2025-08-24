from typing import Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model_dal import AuthDal
from db import AuthAccountDB


async def __get_auth_account_by_auth_id(auth_id: UUID, session: AsyncSession) -> Union[AuthAccountDB, None]:
    async with session.begin():
        auth_dal = AuthDal(session)
        auth_account = await auth_dal.get_auth_account_by_auth_id(
            auth_id=auth_id,
        )
        return auth_account
