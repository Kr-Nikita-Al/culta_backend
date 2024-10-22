import uuid
import datetime

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Time
from sqlalchemy.dialects.postgresql import UUID

from db.base_model import Base
from utils.constants import EMPTY_UUID


############################
# БЛОК ОПИСАНИЯ МОДЕЛЕЙ БД #
############################


class CompanyDB(Base):
    __tablename__ = 'company'

    company_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    company_name = Column(String(20), nullable=False)
    address = Column(String(50), nullable=False)
    phone = Column(String(12), nullable=False)
    email = Column(String(35), nullable=False)
    age_limit = Column(Boolean, default=True)
    work_state = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    order_number = Column(Integer, default=-1)

    # Connection fields
    main_screen_id = Column(Integer, default=-1)
    group_id = Column(Integer, default=-1)
    company_image = Column(String, default="")
    company_icon = Column(String, default="")

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.datetime.now())
    time_updated = Column(DateTime(timezone=True), default=datetime.datetime.now(), onupdate=datetime.datetime.now())
    start_time = Column(Time(), default=datetime.time(9, 0, 0))
    over_time = Column(Time(), default=datetime.time(18, 0, 0))