"""One versioned floor plan per company and whole-table reservations."""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base_model import Base
from db.check_model import utc_now


class FloorPlanDB(Base):
    __tablename__ = 'floor_plan'
    __table_args__ = (CheckConstraint('width BETWEEN 300 AND 4000 AND height BETWEEN 200 AND 2400', name='ck_floor_plan_size'),)
    company_id = Column(UUID(as_uuid=True), ForeignKey('company.company_id', ondelete='RESTRICT'), primary_key=True)
    version = Column(Integer, nullable=False, default=0)
    rooms = Column(JSONB, nullable=False, default=list, server_default='[]')
    width = Column(Integer, nullable=False, default=1000, server_default='1000')
    height = Column(Integer, nullable=False, default=600, server_default='600')


class DiningTableDB(Base):
    __tablename__ = 'dining_table'
    __table_args__ = (
        UniqueConstraint('table_id', 'company_id', name='uq_dining_table_scope'),
        CheckConstraint("shape IN ('square', 'rectangle', 'circle')", name='ck_dining_table_shape'),
        CheckConstraint('seats BETWEEN 1 AND 24', name='ck_dining_table_seats'),
        CheckConstraint('x BETWEEN 0 AND 4000 AND y BETWEEN 0 AND 2400 AND width BETWEEN 50 AND 220 AND height BETWEEN 50 AND 220', name='ck_dining_table_geometry'),
    )
    table_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('company.company_id', ondelete='RESTRICT'), nullable=False, index=True)
    label = Column(String(40), nullable=False)
    order_qr_hash = Column(String(64), nullable=True)
    shape = Column(String(16), nullable=False)
    seats = Column(Integer, nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class ReservationDB(Base):
    __tablename__ = 'reservation'
    __table_args__ = (
        ForeignKeyConstraint(['table_id', 'company_id'], ['dining_table.table_id', 'dining_table.company_id'], ondelete='RESTRICT'),
        UniqueConstraint('company_id', 'creator_id', 'request_id', name='uq_reservation_request'),
        CheckConstraint('ends_at > starts_at', name='ck_reservation_interval'),
        CheckConstraint('guests BETWEEN 1 AND 24', name='ck_reservation_guests'),
        CheckConstraint("status IN ('confirmed', 'seated', 'completed', 'canceled')", name='ck_reservation_status'),
        Index('ix_reservation_company_time', 'company_id', 'starts_at', 'ends_at'),
    )
    reservation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    table_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=True)
    guest_name = Column(String(100), nullable=False)
    guest_phone = Column(String(30), nullable=False)
    guests = Column(Integer, nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, default='confirmed')
    version = Column(Integer, nullable=False, default=1)
    creator_id = Column(UUID(as_uuid=True), ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False)
    updater_id = Column(UUID(as_uuid=True), ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False)
    time_created = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    time_updated = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
