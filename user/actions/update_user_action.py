from typing import Dict, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from User.db.model_dal import UserDAL

async def _update_user(updated_user_params: Dict, user_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        user_dal = UserDAL(session)
        updated_user_id = await user_dal.update_user(
            user_id=user_id, **updated_user_params
        )
        return updated_user_id