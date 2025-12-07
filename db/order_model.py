import uuid
import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float
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


class OrderDB(Base):
    __tablename__ = 'orders'
    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    comment = Column(String(500), default='')
    cocking_time = Column(Integer, default=0)
    status = Column(SQLEnum(STATUS_TYPE), default=STATUS_TYPE.CREATED, nullable=False)

    # Connection fields
    company_id = Column(ForeignKey('company.company_id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    staff_id = Column(UUID(as_uuid=True), nullable=False)
    price = Column(Float, default=0)
    bonus_transaction = Column(Float, default=0)

    # Relationships
    order_items = relationship("OrderProductAssociationDB", back_populates="order_info")

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.datetime.now())
    time_updated = Column(DateTime(timezone=True), default=datetime.datetime.now(), onupdate=datetime.datetime.now())

