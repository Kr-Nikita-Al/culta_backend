import uuid

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint, String, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base_model import Base


class OrderProductAssociationDB(Base):
    __tablename__ = 'order_product_association'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(ForeignKey('orders.order_id'), nullable=False)
    product_card_id = Column(ForeignKey("product_card.product_card_id"), nullable=False)
    quantity = Column(Integer, default=0)
    # NULL snapshots identify legacy positions; do not invent historical prices.
    product_title = Column(String(35), nullable=True)
    unit_price = Column(Numeric(18, 2), nullable=True)
    unit_cost_price = Column(Numeric(18, 2), nullable=True)
    line_total = Column(Numeric(18, 2), nullable=True)

    order_info = relationship("OrderDB", back_populates="order_items")
    product_info = relationship("ProductCardDB", back_populates="order_items")

    __table_args__ = (
        UniqueConstraint('order_id', 'product_card_id', name='uq_order_product'),
        CheckConstraint(
            '(product_title IS NULL AND unit_price IS NULL AND unit_cost_price IS NULL AND line_total IS NULL) OR '
            '(product_title IS NOT NULL AND unit_price IS NOT NULL AND unit_cost_price IS NOT NULL AND line_total IS NOT NULL '
            'AND quantity IS NOT NULL AND quantity >= 0 '
            'AND unit_price BETWEEN 0 AND 9999999999999999.99 '
            'AND unit_cost_price BETWEEN 0 AND 9999999999999999.99 '
            'AND line_total BETWEEN 0 AND 9999999999999999.99 AND line_total = unit_price * quantity)',
            name='ck_order_position_snapshot'),
    )
