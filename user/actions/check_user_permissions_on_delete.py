from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from user_role.actions import __is_exist_user_role
from utils.constants import EMPTY_UUID, PortalRole


async def __check_user_permissions_on_delete(target_user: UserDB, current_user: UserDB, db: AsyncSession) -> bool:
    """
    Удаления клиента:
    1) себя может удалить любой пользователь, кроме супер админа
    2) другого пользователя может удалить супер админ
    :param target_user: удаляемый пользователь
    :param current_user: пользователь, который хочет удалить
    :param db: сессия
    :return: возможность удалить пользователя
    """
    # check super_admin role
    is_exist_super_admin_role = await __is_exist_user_role(target_user.user_id, EMPTY_UUID,
                                                           PortalRole.ROLE_PORTAL_SUPER_ADMIN, db)
    if is_exist_super_admin_role:
        raise HTTPException(status_code=406,
                            detail='Super admin can not be deleted via API')
    elif target_user.user_id != current_user.user_id:
        is_exist_super_admin_role = await __is_exist_user_role(current_user.user_id, EMPTY_UUID,
                                                               PortalRole.ROLE_PORTAL_SUPER_ADMIN, db)
        # check super_admin deactivate
        if not is_exist_super_admin_role:
            return False
    return True

