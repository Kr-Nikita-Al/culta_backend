import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import ARRAY
from typing import List

from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

from db.base_model import Base
from utils.constants import PortalRole
from utils.constants import EMPTY_UUID


############################
# БЛОК ОПИСАНИЯ МОДЕЛЕЙ БД #
############################


class UserDB(Base):
    __tablename__ = 'user'

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    phone = Column(String(12), nullable=False)
    email = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    hashed_password = Column(String, nullable=False)
    roles = Column(ARRAY(String), nullable=False)

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.now())
    time_updated = Column(DateTime(timezone=True), default=datetime.now(), onupdate=datetime.now())

    # Validation
    @property
    def is_super_admin(self) -> bool:
        return PortalRole.ROLE_PORTAL_SUPER_ADMIN is self.roles

    @property
    def is_admin(self) -> bool:
        return PortalRole.ROLE_PORTAL_ADMIN in self.roles

    @property
    def is_staff(self) -> bool:
        return PortalRole.ROLE_PORTAL_STAFF in self.roles

    # Roles methods
    def add_admin_privileges_to_model(self) -> List:
        return set(self.roles + [PortalRole.ROLE_PORTAL_ADMIN])

    def remove_admin_privileges_from_model(self) -> List:
        return set(self.roles) - {PortalRole.ROLE_PORTAL_ADMIN}

    def add_staff_privileges_to_model(self) -> List:
        return set(self.roles + [PortalRole.ROLE_PORTAL_STAFF])

    def remove_staff_privileges_from_model(self) -> List:
        return set(self.roles) - {PortalRole.ROLE_PORTAL_STAFF}