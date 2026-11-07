"""Append-only application audit trail; existing orders are not backfilled."""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, CheckConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID
from db.base_model import Base


class OrderStatusHistoryDB(Base):
    __tablename__ = 'order_status_history'
    __table_args__ = (
        CheckConstraint("old_status IS NULL OR old_status IN ('created','processing','completed','canceled','closed')", name='ck_history_old_status'),
        CheckConstraint("new_status IN ('created','processing','completed','canceled','closed')", name='ck_history_new_status'),
        CheckConstraint('old_status IS NULL OR old_status <> new_status', name='ck_history_transition'),
        Index('ix_history_order_time', 'order_id', 'changed_at', 'event_id'),
    )
    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(ForeignKey('orders.order_id', ondelete='RESTRICT'), nullable=False)
    old_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp())
    reason = Column(String(500), nullable=True)
