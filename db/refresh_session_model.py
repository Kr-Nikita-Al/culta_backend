import uuid
from sqlalchemy import Column, DateTime, Boolean, String, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.base_model import Base


class RefreshSessionDB(Base):
    __tablename__ = 'refresh_session'
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('user.user_id'), nullable=False)
    token_hash = Column(String(64), nullable=False)
    credential_hash = Column(String(64), nullable=False)
    used_hashes = Column(JSON, nullable=False, default=list)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
