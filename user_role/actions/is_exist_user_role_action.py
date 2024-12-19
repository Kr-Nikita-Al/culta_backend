from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user_role.model_dal import UserRoleDAL
from utils.constants import PortalRole


async def __is_exist_user_role(user_id: UUID, company_id: UUID, role: PortalRole, session: AsyncSession) -> bool:
    async with session.begin():
        user_role_dal = UserRoleDAL(session)
        return await user_role_dal.is_exist_user_role(
            user_id=user_id,
            company_id=company_id,
            role=role
        )