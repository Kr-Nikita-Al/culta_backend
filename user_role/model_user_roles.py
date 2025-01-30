from typing import List
from utils.constants import PortalRole


class UserRoleModel:
    def __init__(self, user_roles: List):
        self.user_roles = user_roles

    @property
    def is_super_admin(self) -> bool:
        return PortalRole.PORTAL_ROLE_SUPER_ADMIN in self.user_roles

    @property
    def is_admin(self) -> bool:
        return PortalRole.PORTAL_ROLE_ADMIN in self.user_roles

    @property
    def is_moderator(self) -> bool:
        return PortalRole.PORTAL_ROLE_MODERATOR in self.user_roles


