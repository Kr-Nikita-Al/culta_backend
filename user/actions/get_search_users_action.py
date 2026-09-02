from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user.interface_response import UserSearchResponse
from user.model_dal import UserDAL


async def __get_search_users(search: str, company_id: UUID, session: AsyncSession):
    async with session.begin():
        user_dal = UserDAL(session)
        users = await user_dal.search_users_by_name_or_id(search)

        users_response = []
        for user in users:
            # Фильтруем роли только для компании администратора
            company_roles = [
                {"company_id": role.company_id, "role": role.role}
                for role in user.roles
                if role.company_id == company_id and role.is_active
            ]
            users_response.append(UserSearchResponse(
                user_id=user.user_id,
                name=user.name,
                time_created=user.time_created,
                current_roles=company_roles
            ))
    return users_response

