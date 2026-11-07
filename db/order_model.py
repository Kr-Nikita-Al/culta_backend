from utils.timestamps import utc_now
from decimal import Decimal
import uuid
import datetime

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Numeric, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum as PyEnum
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, relationship

from db.base_model import Base
from utils.constants import EMPTY_UUID


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class STATUS_TYPE(PyEnum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELED = "canceled"
    CLOSED = "closed"


STATUS_VALUES = {status.value for status in STATUS_TYPE}


class OrderDB(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        UniqueConstraint('user_id', 'client_request_id', name='uq_order_client_request'),
        ForeignKeyConstraint(['table_id', 'company_id'], ['dining_table.table_id', 'dining_table.company_id'], name='fk_order_table_scope', ondelete='RESTRICT'),
        ForeignKeyConstraint(['check_id', 'company_id', 'user_id'],
                             ['checks.check_id', 'checks.company_id', 'checks.user_id'],
                             name='fk_order_check_scope', ondelete='RESTRICT', deferrable=True, initially='DEFERRED'),
        ForeignKeyConstraint(['check_id', 'company_id'], ['checks.check_id', 'checks.company_id'],
                             name='fk_order_check_company', ondelete='RESTRICT'),
    )
    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_context = Column(String(16), nullable=True)
    table_id = Column(UUID(as_uuid=True), nullable=True)
    client_request_id = Column(UUID(as_uuid=True), nullable=True)
    client_request_hash = Column(String(64), nullable=True)
    check_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Properties
    comment = Column(String(500), default='')
    cocking_time = Column(Integer, default=0)
    status = Column(SQLEnum(STATUS_TYPE), default=STATUS_TYPE.CREATED, nullable=False)

    # Connection fields
    company_id = Column(ForeignKey('company.company_id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    staff_id = Column(UUID(as_uuid=True), nullable=False)
    price = Column(Numeric(18, 2), CheckConstraint('price >= 0 AND price <= 9999999999999999.99', name='ck_order_price_range'), default=Decimal('0.00'))
    bonus_transaction = Column(Numeric(18, 2), CheckConstraint('bonus_transaction >= 0 AND bonus_transaction <= 9999999999999999.99', name='ck_order_bonus_transaction_range'), default=Decimal('0.00'))

    # Relationships
    order_items = relationship("OrderProductAssociationDB", back_populates="order_info")
    check_info = relationship('CheckDB', back_populates='orders',
                             primaryjoin='and_(CheckDB.check_id == OrderDB.check_id, CheckDB.company_id == OrderDB.company_id)')

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=utc_now)
    time_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
