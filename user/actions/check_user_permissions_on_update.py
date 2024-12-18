from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from user_role.actions import __is_exist_user_role
from utils.constants import EMPTY_UUID, PortalRole


async def __check_user_permissions_on_update(target_user: UserDB, current_user: UserDB, db: AsyncSession) -> bool:
    """
    Обновление пользователя:
    1) свои данные может обновить любой пользователь
    2) другого пользователя может обновить супер админ
    :param target_user: обновляемый пользователь
    :param current_user: пользователь, который хочет обновить данные
    :param db: сессия
    :return: возможность обновить данные пользователя
    """
    if target_user.user_id != current_user.user_id:
        is_exist_super_admin_role = await __is_exist_user_role(current_user.user_id, EMPTY_UUID,
                                                               PortalRole.ROLE_PORTAL_SUPER_ADMIN, db)
        # check super_admin role
        if not is_exist_super_admin_role:
            return False
    return True
