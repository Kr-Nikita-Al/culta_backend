from user_role.model_user_roles import UserRoleModel
from utils.constants import PortalRole


async def __check_permissions_granting_or_revoking_user_roles(user_roles: UserRoleModel, promo_or_demo_role: PortalRole,
                                                              is_grant: bool = True) -> bool:
    """
    Метод проверки ролей пользователя, который выдает/отзывает роль
    :param is_grant: выдача прав
    :param user_roles: роли пользователя
    :param promo_or_demo_role: делегируемая роль
    :return: bool
    """
    # Выдать/отозвать роль владельца может только супер админ
    if promo_or_demo_role == PortalRole.PORTAL_ROLE_OWNER and user_roles.is_super_admin:
        return True
    # Выдать/отозвать роль администратора может супер админ, владелец.
    # Другой администратор заведения может только выдать роль
    elif promo_or_demo_role == PortalRole.PORTAL_ROLE_ADMIN and (user_roles.is_super_admin or
                                                                 user_roles.is_admin and is_grant or
                                                                 user_roles.is_owner):
        return True
    # Выдать/отозвать роль модератора может владелец или администратор заведения
    elif promo_or_demo_role == PortalRole.PORTAL_ROLE_MODERATOR and (user_roles.is_admin or user_roles.is_owner):
        return True
    # Выдать/отозвать роль официанта может владелец или администратор заведения
    elif promo_or_demo_role == PortalRole.PORTAL_ROLE_WAITER and (user_roles.is_admin or user_roles.is_owner):
        return True
    # Выдать/отозвать роль повара может владелец или администратор заведения
    elif promo_or_demo_role == PortalRole.PORTAL_ROLE_COOK and (user_roles.is_admin or user_roles.is_owner):
        return True
    return False
