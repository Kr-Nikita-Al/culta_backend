import uuid
from enum import Enum

EMPTY_UUID = uuid.UUID(int=0)


class PortalRole(str, Enum):
    PORTAL_ROLE_SUPER_ADMIN = 'PORTAL_ROLE_SUPER_ADMIN'
    PORTAL_ROLE_ADMIN = 'PORTAL_ROLE_ADMIN'  # любые действия в своем заведении, кроме удаления и создания компании
    PORTAL_ROLE_MODERATOR = 'PORTAL_ROLE_MODERATOR'  # создание product_card и экранов для их размещения

    PORTAL_ROLE_USER = 'PORTAL_ROLE_USER'
