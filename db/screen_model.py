from utils.timestamps import utc_now
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base
from utils.constants import EMPTY_UUID


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################

class ScreenDB(Base):
    __tablename__ = 'screen'
    screen_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    is_active = Column(Boolean, nullable=False, default=True, server_default='true')
    is_visible = Column(Boolean, nullable=False, default=True, server_default='true')

    # Properties
    screen_title = Column(String(100), default='')
    screen_sub_title = Column(String(), nullable=False, default='')
    screen_order_number = Column(Integer, default=0)
    editor_version = Column(Integer, nullable=False, default=0, server_default='0')

    # Connection fields
    company_id = Column(ForeignKey('company.company_id'), primary_key=True, nullable=False)
    company_info = relationship("CompanyDB", back_populates="screens", lazy="joined")
    company_group_id = Column(Integer, default=-1)

    # Navigation fields
    containers = relationship("ContainerDB", back_populates="screen_info", lazy="joined")

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=utc_now)
    time_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
