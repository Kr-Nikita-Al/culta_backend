import uuid
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List

from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from user.const.portal_role import PortalRole
from db.base_model import Base

############################
# БЛОК ОПИСАНИЯ МОДЕЛЕЙ БД #
############################


class UserDB(Base):
    __tablename__ = 'user'

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4())
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    phone = Column(String(12), nullable=False)
    email = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    hashed_password = Column(String, nullable=False)
    roles = Column(ARRAY(String), nullable=False)
    creator_id = Column(UUID(as_uuid=True), default=uuid.uuid4())
    updater_id = Column(UUID(as_uuid=True), default=uuid.uuid4())
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

    # @property
    # def is_super_admin(self) -> bool:
    #     return PortalRole.ROLE_PORTAL_SUPER_ADMIN is self.roles
    #
    # @property
    # def is_admin(self) -> bool:
    #     return PortalRole.ROLE_PORTAL_ADMIN in self.roles
    #
    # @property
    # def is_staff(self) -> bool:
    #     return PortalRole.ROLE_PORTAL_STAFF in self.roles
    #
    # def add_admin_privileges_to_model(self) -> List:
    #     return set(self.roles + [PortalRole.ROLE_PORTAL_ADMIN])
    #
    # def remove_admin_privileges_from_model(self) -> List:
    #     return set(self.roles) - {PortalRole.ROLE_PORTAL_ADMIN}
    #
    # def add_staff_privileges_to_model(self) -> List:
    #     return set(self.roles + [PortalRole.ROLE_PORTAL_STAFF])
    #
    # def remove_staff_privileges_from_model(self) -> List:
    #     return set(self.roles) - {PortalRole.ROLE_PORTAL_STAFF}