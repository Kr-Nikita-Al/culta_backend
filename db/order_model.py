import uuid
import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum as PyEnum
from sqlalchemy import Enum as SQLEnum

from db.base_model import Base
from utils.constants import EMPTY_UUID


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class STATUS_TYPE(PyEnum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"


class OrderDB(Base):
    __tablename__ = 'order'
    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    comment = Column(String(500), default='')
    cocking_time = Column(Integer, default=0)
    status = Column(SQLEnum(STATUS_TYPE), default=STATUS_TYPE.CREATED, nullable=False)

    # Connection fields
    company_id = Column(ForeignKey('company.company_id'), primary_key=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    staff_id = Column(UUID(as_uuid=True), nullable=False)

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.datetime.now())
    time_updated = Column(DateTime(timezone=True), default=datetime.datetime.now(), onupdate=datetime.datetime.now())

