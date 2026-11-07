from sqlalchemy import Column, DateTime, ForeignKeyConstraint, String, Index
from sqlalchemy.dialects.postgresql import UUID
from db.base_model import Base


class ImageUploadReservationDB(Base):
    """Only new presigned uploads are eligible for abandoned-upload cleanup."""
    __tablename__ = 'image_upload_reservation'
    __table_args__ = (ForeignKeyConstraint(
        ['image_id', 'company_id'], ['image.image_id', 'image.company_id'],
        ondelete='CASCADE'), Index('ix_image_upload_reservation_cleanup', 'company_id', 'cleanup_after'))
    image_id = Column(UUID(as_uuid=True), primary_key=True)
    company_id = Column(UUID(as_uuid=True), primary_key=True)
    object_key = Column(String(1100), nullable=False)
    cleanup_after = Column(DateTime(timezone=True), nullable=False)
