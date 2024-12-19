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


class UserRoleDB(Base):
    __tablename__ = 'user_role'

    relation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    user_id = Column(UUID(as_uuid=True), nullable=False)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.now())

    # Validation
    @property
    def is_super_admin(self) -> bool:
        return self.role == PortalRole.PORTAL_ROLE_SUPER_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.role == PortalRole.PORTAL_ROLE_ADMIN

    @property
    def is_staff(self) -> bool:
        return self.role == PortalRole.PORTAL_ROLE_STAFF
