"""Append-only audit of the application's shared bonus wallet."""
import uuid

from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, ForeignKeyConstraint, CheckConstraint, Index, text, func
from sqlalchemy.dialects.postgresql import UUID
from db.base_model import Base


class BonusTransactionDB(Base):
    __tablename__ = 'bonus_transaction'
    __table_args__ = (
        ForeignKeyConstraint(['check_id', 'company_id', 'user_id'],
                             ['checks.check_id', 'checks.company_id', 'checks.user_id'], ondelete='RESTRICT'),
        CheckConstraint("kind IN ('opening', 'welcome', 'accrual', 'redemption', 'refund', 'adjustment')", name='ck_bonus_kind'),
        CheckConstraint('balance_after = balance_before + amount', name='ck_bonus_arithmetic'),
        CheckConstraint('balance_before BETWEEN 0 AND 9999999999999999.99 AND balance_after BETWEEN 0 AND 9999999999999999.99', name='ck_bonus_balances'),
        CheckConstraint("(kind IN ('opening', 'welcome') AND company_id IS NULL AND check_id IS NULL AND balance_before = 0) OR (kind = 'adjustment' AND company_id IS NOT NULL AND actor_id IS NOT NULL AND amount <> 0) OR (kind IN ('accrual', 'refund') AND check_id IS NOT NULL AND company_id IS NOT NULL AND amount > 0) OR (kind = 'redemption' AND check_id IS NOT NULL AND company_id IS NOT NULL AND amount < 0)", name='ck_bonus_scope'),
        CheckConstraint("kind <> 'welcome' OR amount = 500", name='ck_bonus_welcome'),
        Index('uq_bonus_initial', 'user_id', unique=True, postgresql_where=text("kind IN ('opening', 'welcome')")),
        Index('uq_bonus_request', 'user_id', 'request_id', unique=True),
        Index('uq_bonus_check_settlement', 'check_id', 'kind', unique=True,
              postgresql_where=text("kind IN ('accrual', 'redemption')")),
    )
    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False, index=True)
    company_id = Column(ForeignKey('company.company_id', ondelete='RESTRICT'), nullable=True)
    check_id = Column(UUID(as_uuid=True), nullable=True)
    actor_id = Column(ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=True)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    kind = Column(String(16), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    balance_before = Column(Numeric(18, 2), nullable=False)
    balance_after = Column(Numeric(18, 2), nullable=False)
    reason = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
