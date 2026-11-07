import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, Integer, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from db.base_model import Base
from db.check_model import utc_now


class AccountLinkFlowDB(Base):
    __tablename__ = 'account_link_flow'
    flow_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(ForeignKey('user.user_id'), nullable=False)
    provider = Column(String(20), nullable=False)
    target_user_id = Column(ForeignKey('user.user_id'), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed = Column(Boolean, nullable=False, default=False)


class AccountSuggestionDB(Base):
    __tablename__ = 'account_suggestion'
    __table_args__ = (UniqueConstraint('left_id','right_id',name='uq_account_suggestion_pair'),
        CheckConstraint('left_id < right_id',name='ck_account_suggestion_order'),
        CheckConstraint("status IN ('pending','dismissed','verified')",name='ck_account_suggestion_status'))
    suggestion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    left_id = Column(ForeignKey('user.user_id'), nullable=False)
    right_id = Column(ForeignKey('user.user_id'), nullable=False)
    status = Column(String(16), nullable=False, default='pending')
    changed_by = Column(ForeignKey('user.user_id'), nullable=True)
    verification_attempts = Column(Integer, nullable=False, default=0, server_default='0')
    verify_after = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
