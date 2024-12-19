from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user_role.interface_response import GetUserRolesResponse
from user_role.model_dal import UserRoleDAL


async def __get_user_roles(user_id: UUID, session: AsyncSession) -> List[GetUserRolesResponse]:
    async with session.begin():
        user_role_dal = UserRoleDAL(session)
        return await user_role_dal.get_user_roles(
            user_id=user_id
        )
