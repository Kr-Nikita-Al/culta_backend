import uuid

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base

###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class ContainerDB(Base):
    __tablename__ = 'container'
    container_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    container_title = Column(String(100), default='')
    container_sub_title = Column(String(100), default='')
    container_type = Column(String(35), default='')
    container_order = Column(Integer, default=0)

    # Connection fields
    items = relationship("ItemDB", back_populates="container_info", lazy="joined")

    screen_id = Column(ForeignKey("screen.screen_id"), primary_key=True, nullable=False)
    screen_info = relationship("ScreenDB", back_populates="containers", lazy="joined")
