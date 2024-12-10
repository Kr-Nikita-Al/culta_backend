from fastapi import HTTPException

from db import UserDB


def __check_user_permissions_on_delete(target_user: UserDB, current_user: UserDB) -> bool:
    """
    Логика удаления:
    1) себя может удалить любой пользователь, кроме супер админа
    2) другого пользователя может удалить админ (только базового) или супер админ (админа или базового)
    :param target_user: удаляемый пользователь
    :param current_user: пользователь, который хочет удалить
    :return:
    """
    # check super admin role
    if target_user.is_super_admin:
        raise HTTPException(status_code=406,
                            detail='Super admin can not be deleted via API')
    elif target_user.user_id != current_user.user_id:
        # check admin roles
        if not(current_user.is_admin or current_user.is_super_admin):
            return False
        # check admin deactivate super_admin or another admin
        if current_user.is_admin and (target_user.is_super_admin or target_user.is_admin):
            return False
    return True

