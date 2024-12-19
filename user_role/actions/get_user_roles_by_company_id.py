from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user_role.model_dal import UserRoleDAL


async def __get_user_roles_by_company_id(user_id: UUID, company_id: UUID, session: AsyncSession) -> List:
    async with session.begin():
        user_role_dal = UserRoleDAL(session)
        user_roles = await user_role_dal.get_user_roles(
            user_id=user_id
        )
        if user_roles is not None:
            return [user_role.role for user_role in user_roles if user_role.company_id == company_id]
        return []
