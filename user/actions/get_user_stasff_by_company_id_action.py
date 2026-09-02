from typing import Union, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from user.interface_response import UserWithRolesResponse
from user.model_dal import UserDAL


async def __get_user_staff_by_company_id(company_id: UUID, session: AsyncSession) -> Union[
    List[UserWithRolesResponse], None]:
    async with session.begin():
        user_dal = UserDAL(session)
        users = await user_dal.get_user_staff(
            company_id=company_id,
        )
        if users is not None:
            response = []
            for user in users:
                company_roles = [role.role
                                 for role in user.roles if role.company_id == company_id and role.is_active == True]
                if company_roles:
                    response.append(UserWithRolesResponse(user_id=user.user_id, name=user.name,
                                                          surname=user.surname, roles=company_roles))
            return response
        return []
