import uuid
from enum import Enum as PyEnum
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import relationship
from db.base_model import Base
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy import Enum as SQLEnum

from utils.constants import EMPTY_UUID


class AuthProvider(PyEnum):
    GOOGLE = "google"
    YANDEX = "yandex"
    TELEGRAM = "telegram"
    APPLE = "apple"


class AuthAccountDB(Base):
    __tablename__ = 'oauth_accounts'
    auth_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(SQLEnum(AuthProvider), nullable=False)
    provider_user_id = Column(String)
    user_id = Column(ForeignKey('user.user_id'), primary_key=True, nullable=False)
    user = relationship("UserDB", back_populates="accounts", lazy="selectin")
