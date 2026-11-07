from utils.timestamps import utc_now
from decimal import Decimal
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Numeric, CheckConstraint, Integer
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
    email = Column(String, nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    account_status = Column(String(16), CheckConstraint("account_status IN ('pending','confirmed','blocked','deleted')", name='ck_user_account_status'), nullable=False, default='pending', server_default='pending')
    email_code_hash = Column(String(64), nullable=True)
    email_code_expires = Column(DateTime(timezone=True), nullable=True)
    email_code_sent_at = Column(DateTime(timezone=True), nullable=True)
    email_code_attempts = Column(Integer, nullable=False, default=0, server_default='0')
    hashed_password = Column(String, nullable=False)
    password_code_hash = Column(String(64), nullable=True)
    password_code_expires = Column(DateTime(timezone=True), nullable=True)
    password_code_sent_at = Column(DateTime(timezone=True), nullable=True)
    password_code_attempts = Column(Integer, nullable=False, default=0, server_default='0')
    bonus_balance = Column(Numeric(18, 2), CheckConstraint('bonus_balance >= 0 AND bonus_balance <= 9999999999999999.99', name='ck_user_bonus_balance_range'), default=Decimal('500.00'))
    qr_code = Column(String, default='')

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=utc_now)
    time_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    accounts = relationship("AuthAccountDB", back_populates="user")
    roles = relationship("UserRoleDB", foreign_keys="[UserRoleDB.user_id]",
                         primaryjoin="UserDB.user_id == UserRoleDB.user_id",
                         lazy="selectin")
