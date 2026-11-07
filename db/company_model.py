from utils.timestamps import utc_now
from decimal import Decimal
import uuid
import datetime

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Time, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from db.base_model import Base
from utils.constants import EMPTY_UUID


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class CompanyDB(Base):
    __tablename__ = 'company'
    __table_args__ = (CheckConstraint('bonus_accrual_perc <= bonus_payment_perc', name='ck_company_bonus_ratio'),)
    loyalty_levels = Column(JSONB, nullable=False, default=list, server_default='[]')
    infrastructure_version = Column(Integer, nullable=False, default=0, server_default='0')
    orders_enabled = Column(Boolean, nullable=False, default=True, server_default='true')
    reservations_enabled = Column(Boolean, nullable=False, default=True, server_default='true')
    images_enabled = Column(Boolean, nullable=False, default=True, server_default='true')

    company_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    edit_lease_token = Column(UUID(as_uuid=True), nullable=True)
    edit_lease_user_id = Column(UUID(as_uuid=True), nullable=True)
    edit_lease_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Properties
    company_name = Column(String(20), nullable=False)
    address = Column(String(50), nullable=False)
    phone = Column(String(12), nullable=False)
    email = Column(String(35), nullable=False)
    order_number = Column(Integer, default=-1)
    city = Column(String(50), default="Москва")
    region = Column(String(50), default="Москва и Московская обл.")

    # Connection fields
    basic_screen_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    group_id = Column(Integer, default=-1)

    image_picture_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    image_icon_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)

    # Navigation fields
    screens = relationship("ScreenDB", back_populates="company_info", lazy="joined")

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=utc_now)
    time_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    start_time = Column(Time(), default=datetime.time(9, 0, 0))
    over_time = Column(Time(), default=datetime.time(18, 0, 0))

    # Settings
    service_type = Column(String(20), CheckConstraint("service_type IN ('self_service', 'waiter_service')", name='ck_company_service_type'), nullable=False, default='self_service', server_default='self_service')
    work_state = Column(Boolean, default=True)
    age_limit = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    is_can_client_create_order = Column(Boolean, default=False)
    allow_client_orders_inside = Column(Boolean, nullable=False, default=False, server_default='false')
    allow_client_orders_outside = Column(Boolean, nullable=False, default=False, server_default='false')
    bonus_payment_perc = Column(Numeric(5, 2), CheckConstraint('bonus_payment_perc >= 0 AND bonus_payment_perc <= 100', name='ck_company_bonus_payment_perc_range'), default=Decimal('0.00'))
    bonus_accrual_perc = Column(Numeric(5, 2), CheckConstraint('bonus_accrual_perc >= 0 AND bonus_accrual_perc <= 100', name='ck_company_bonus_accrual_perc_range'), default=Decimal('0.00'))
