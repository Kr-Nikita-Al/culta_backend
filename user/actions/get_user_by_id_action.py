from typing import Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from User.db.model_dal import UserDAL
from User.db.model_db import UserDB

async def _get_user_by_id(user_id: UUID, session: AsyncSession) -> Union[UserDB, None]:
    async with session.begin():
        user_dal = UserDAL(session)
        user = await user_dal.get_user_by_id(
            user_id=user_id,
        )
        if user is not None:
            return user