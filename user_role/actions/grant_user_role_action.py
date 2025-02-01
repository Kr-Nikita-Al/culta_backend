from sqlalchemy.ext.asyncio import AsyncSession

from user_role.interface_request import GrantUserRoleRequest
from user_role.interface_response import GrantUserRoleResponse
from user_role.model_dal import UserRoleDAL


async def __grant_user_role(user_role_body: GrantUserRoleRequest, session: AsyncSession) -> GrantUserRoleResponse:
    async with session.begin():
        user_role_dal = UserRoleDAL(session)
        user_role_db = await user_role_dal.grant_user_role(
            user_id=user_role_body.user_id,
            company_id=user_role_body.company_id,
            role=user_role_body.role,
            creator_id=user_role_body.creator_id
        )
        return GrantUserRoleResponse(
            granted_user_id=user_role_db.user_id
        )
