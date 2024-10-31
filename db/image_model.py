import uuid
from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base
from utils.constants import EMPTY_UUID


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class ImageDB(Base):
    __tablename__ = 'image'

    image_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    title = Column(String(100), default='')
    type_col = Column(String(100), default='')
    image_type = Column(String(100), default='')
    url = Column(String(200), default='')
    resolution = Column(String(100), default='')
    tags = Column(String(100), default='')
    order_number = Column(Integer, default=0)
    size = Column(Integer, default=0)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)

    # Connection fields
    company_group_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)

    company_id = Column(ForeignKey('company.company_id'), primary_key=True, nullable=False)
    company_info = relationship("CompanyDB", back_populates="images", lazy="joined")

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.now())



