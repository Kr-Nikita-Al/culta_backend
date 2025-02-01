from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from user_role.actions import __get_user_role_model
from utils.constants import EMPTY_UUID


async def __check_permission_navigation(user_id: UUID, session: AsyncSession, company_id: UUID = EMPTY_UUID) -> bool:
    """
    Редактировать навигацию экранов может админ или модератор заведения
    :param user_id: id пользователя
    :param session: сессия
    :param company_id: id компании
    :return: возможность совершения действия
    """
    cur_user_role_model = await __get_user_role_model(user_id=user_id, session=session,
                                                      company_id=company_id)
    return cur_user_role_model.is_admin or cur_user_role_model.is_moderator
