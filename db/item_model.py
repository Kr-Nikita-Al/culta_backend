import uuid

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class ItemDB(Base):
    __tablename__ = 'item'
    item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    item_row_order = Column(Integer, default=0)
    item_column_order = Column(Integer, default=0)
    item_type = Column(String(35), default='')

    # Connection fields
    product_card_id = Column(ForeignKey("product_card.product_card_id"), primary_key=True, nullable=False)
    product_card_info = relationship("ProductCardDB", back_populates="item")
