from sqlalchemy import Column, DateTime, Index, Integer, String
from db.base_model import Base


class AuthRateLimitDB(Base):
    __tablename__ = 'auth_rate_limit'
    __table_args__ = (Index('ix_auth_rate_limit_expires', 'expires_at'),)
    bucket_key = Column(String(64), primary_key=True)
    attempts = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
