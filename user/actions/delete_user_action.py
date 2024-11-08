from typing import Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from user.model_dal import UserDAL

async def _delete_user(user_id, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        user_dal = UserDAL(session)
        deleted_user_id = await user_dal.delete_user(
            user_id=user_id,
        )
        return deleted_user_id