from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user_role.actions import __get_user_roles_by_company_id, __is_exist_user_role
from user_role.model_user_roles import UserRoleModel
from utils.constants import EMPTY_UUID, PortalRole


async def __get_user_role_model(user_id: UUID, session: AsyncSession, company_id: UUID = EMPTY_UUID) -> UserRoleModel:
    user_roles = []
    if company_id != EMPTY_UUID:
        user_roles = await __get_user_roles_by_company_id(user_id, company_id, session)
    if await __is_exist_user_role(user_id, EMPTY_UUID, PortalRole.PORTAL_ROLE_SUPER_ADMIN, session):
        user_roles += [PortalRole.PORTAL_ROLE_SUPER_ADMIN]
    return UserRoleModel(user_roles=user_roles)
