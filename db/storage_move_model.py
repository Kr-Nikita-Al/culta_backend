from uuid import uuid4
from sqlalchemy import Column, String, DateTime, Index, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base_model import Base


class StorageMoveDB(Base):
    """Copy intent and outcome; a journal row is NOT permission to delete a key."""
    __tablename__ = 'storage_move'
    __table_args__ = (
        CheckConstraint("kind IN ('image', 'directory')", name='ck_storage_move_kind'),
        CheckConstraint("status IN ('pending', 'committed')", name='ck_storage_move_status'),
        Index('ix_storage_move_company_created', 'company_id', 'created_at'),
        Index('ix_storage_move_status_created', 'status', 'created_at'),
    )
    operation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    image_id = Column(UUID(as_uuid=True), nullable=True)
    kind = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default='committed', server_default='committed')
    source_key = Column(String(1100), nullable=False)
    destination_key = Column(String(1100), nullable=False)
    copied_keys = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
