"""Financial check; preparation status remains on the individual orders."""
import datetime
import uuid
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Numeric, String, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class CheckDB(Base):
    __tablename__ = 'checks'
    __table_args__ = (
        ForeignKeyConstraint(['table_id', 'company_id'], ['dining_table.table_id', 'dining_table.company_id'], name='fk_check_table_scope', ondelete='RESTRICT'),
        CheckConstraint("order_context IS NULL OR (order_context = 'inside' AND table_id IS NOT NULL) OR (order_context = 'outside' AND table_id IS NULL)", name='ck_check_order_context'),
        UniqueConstraint('check_id', 'company_id', 'user_id', name='uq_check_scope'),
        UniqueConstraint('check_id', 'company_id', name='uq_check_company'),
        CheckConstraint('user_id IS NOT NULL OR (bonus_spent = 0 AND bonus_earned = 0)', name='ck_guest_no_bonuses'),
        CheckConstraint("status IN ('open', 'closed', 'canceled')", name='ck_check_status'),
        CheckConstraint('total_amount IS NULL OR total_amount BETWEEN 0 AND 9999999999999999.99',
                        name='ck_check_total_range'),
        CheckConstraint('paid_amount BETWEEN 0 AND 9999999999999999.99', name='ck_check_paid_range'),
        CheckConstraint('total_amount IS NULL OR paid_amount <= total_amount', name='ck_check_paid_limit'),
        CheckConstraint("(status = 'closed' AND closed_at IS NOT NULL AND total_amount IS NOT NULL) OR "
                        "(status <> 'closed' AND closed_at IS NULL)", name='ck_check_closed_state'),
    )

    check_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loyalty_level_name = Column(String(80), nullable=True)
    order_context = Column(String(16), nullable=True)
    table_id = Column(UUID(as_uuid=True), nullable=True)
    company_id = Column(ForeignKey('company.company_id', ondelete='RESTRICT'), nullable=False, index=True)
    user_id = Column(ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=True)
    guest_name = Column(String(100), nullable=True)
    status = Column(String(16), nullable=False, default='open', server_default='open')
    service_type = Column(String(20), CheckConstraint("service_type IN ('self_service', 'waiter_service')", name='ck_check_service_type'), nullable=False, default='self_service', server_default='self_service')
    # NULL means not finalized. Do not invent financial history for old orders.
    total_amount = Column(Numeric(18, 2), nullable=True)
    paid_amount = Column(Numeric(18, 2), nullable=False, default=Decimal('0.00'), server_default='0')
    bonus_spent = Column(Numeric(18, 2), CheckConstraint('bonus_spent BETWEEN 0 AND 9999999999999999.99', name='ck_check_bonus_spent'), nullable=False, default=Decimal('0'), server_default='0')
    bonus_earned = Column(Numeric(18, 2), CheckConstraint('bonus_earned BETWEEN 0 AND 9999999999999999.99', name='ck_check_bonus_earned'), nullable=False, default=Decimal('0'), server_default='0')
    # NULL for historical checks, whose program settings cannot be reconstructed.
    bonus_payment_perc = Column(Numeric(5, 2), CheckConstraint('bonus_payment_perc BETWEEN 0 AND 100', name='ck_check_bonus_payment_perc'))
    bonus_accrual_perc = Column(Numeric(5, 2), CheckConstraint('bonus_accrual_perc BETWEEN 0 AND 100', name='ck_check_bonus_accrual_perc'))
    closed_at = Column(DateTime(timezone=True), nullable=True)
    creator_id = Column(ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False)
    updater_id = Column(ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False)
    time_created = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    time_updated = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    # No delete cascade: financial records must not silently erase orders.
    orders = relationship('OrderDB', back_populates='check_info', passive_deletes='all',
                          primaryjoin='and_(CheckDB.check_id == OrderDB.check_id, CheckDB.company_id == OrderDB.company_id)')
