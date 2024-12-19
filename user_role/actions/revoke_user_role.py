from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user_role.interface_request import RevokeUserRoleRequest
from user_role.model_dal import UserRoleDAL


async def __revoke_user_role(user_role_body: RevokeUserRoleRequest, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        user_role_dal = UserRoleDAL(session)
        revoked_user_id = await user_role_dal.revoke_user_role(
            user_id=user_role_body.user_id,
            company_id=user_role_body.company_id,
            role=user_role_body.role
        )
        return revoked_user_id
