from uuid import uuid4
from sqlalchemy import Column, String, DateTime, Index, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base_model import Base


class StorageDeleteDB(Base):
    """Durable outbox: image rows disappear in the same commit as this intent."""
    __tablename__ = 'storage_delete'
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'done')", name='ck_storage_delete_status'),
        Index('ix_storage_delete_company_status', 'company_id', 'status'),
    )
    operation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    prefix = Column(String(1100), nullable=False)
    status = Column(String(16), nullable=False, default='pending', server_default='pending')
    keys = Column(JSONB, nullable=False)
    image_ids = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
