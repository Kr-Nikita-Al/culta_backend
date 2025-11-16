from typing import List
from utils.constants import PortalRole


class UserRoleModel:
    def __init__(self, user_roles: List):
        self.user_roles = user_roles

    @property
    def is_super_admin(self) -> bool:
        return PortalRole.PORTAL_ROLE_SUPER_ADMIN in self.user_roles

    @property
    def is_owner(self) -> bool:
        return PortalRole.PORTAL_ROLE_OWNER in self.user_roles

    @property
    def is_admin(self) -> bool:
        return PortalRole.PORTAL_ROLE_ADMIN in self.user_roles

    @property
    def is_moderator(self) -> bool:
        return PortalRole.PORTAL_ROLE_MODERATOR in self.user_roles

    @property
    def is_waiter(self) -> bool:
        return PortalRole.PORTAL_ROLE_WAITER in self.user_roles

    def check_existing_role(self, role: PortalRole):
        return role in self.user_roles
