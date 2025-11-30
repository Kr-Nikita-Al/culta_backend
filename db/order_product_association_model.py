import uuid

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_model import Base


class OrderProductAssociationDB(Base):
    __tablename__ = 'order_product_association'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(ForeignKey('orders.order_id'), nullable=False)
    product_card_id = Column(ForeignKey("product_card.product_card_id"), nullable=False)
    quantity = Column(Integer, default=0)

    order_info = relationship("OrderDB", back_populates="order_items")
    product_info = relationship("ProductCardDB", back_populates="order_items")

    __table_args__ = (
        UniqueConstraint('order_id', 'product_card_id', name='uq_order_product'),
    )
