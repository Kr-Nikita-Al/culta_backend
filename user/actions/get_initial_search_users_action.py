from typing import Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from user.interface_response import UserSearchResponse
from user.model_dal import UserDAL


async def __get_initial_search_users(company_id: UUID, session: AsyncSession):
    """
    Получить первоначальный список пользователей:
    1. Все сотрудники компании администратора
    2. Последние зарегистрированные пользователи (до лимита)
    """
    async with session.begin():
        user_dal = UserDAL(session)
        # 1. Получаем сотрудников компании (переиспользуем get_user_staff)
        company_users = await user_dal.get_user_staff(company_id)
        # 2. Получаем последних пользователей
        recent_users = await user_dal.get_recent_users()
        # 3. Объединяем и убираем дубликаты
        all_users_dict = {}
        # Сначала добавляем сотрудников компании
        for user in company_users:
            all_users_dict[user.user_id] = user
        # Добавляем последних пользователей
        for user in recent_users:
            if len(all_users_dict) >= 100:
                break
            if user.user_id not in all_users_dict:
                all_users_dict[user.user_id] = user
        # Формируем ответ
        users_response = []
        for user in all_users_dict.values():
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
                current_roles=company_roles  # Только роли в компании админа
            ))

        # Сортируем: сначала сотрудники компании
        users_response.sort(key=lambda x: (
            0 if x.current_roles else 1,  # Сотрудники компании вверху
            x.time_created
        ), reverse=True)

    return users_response
