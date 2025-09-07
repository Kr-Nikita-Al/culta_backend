import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base
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

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.now())
    time_updated = Column(DateTime(timezone=True), default=datetime.now(), onupdate=datetime.now())

    accounts = relationship("AuthAccountDB", back_populates="user")


