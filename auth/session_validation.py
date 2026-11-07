"""Validate session-bound access JWTs without changing legacy token behavior."""
import hashlib
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func
from db.refresh_session_model import RefreshSessionDB


async def require_live_session(db, user, payload):
    if 'sid' not in payload:
        return  # Legacy access tokens remain valid until their original exp.
    try:
        sid = UUID(payload['sid'])
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(401, 'Invalid session')
    async with db.begin():
        session = await db.scalar(select(RefreshSessionDB).where(
            RefreshSessionDB.session_id == sid,
            RefreshSessionDB.user_id == user.user_id,
            RefreshSessionDB.revoked.is_(False),
            RefreshSessionDB.expires_at > func.clock_timestamp()))
        valid = session is not None and session.credential_hash == hashlib.sha256(user.hashed_password.encode()).hexdigest()
    if not valid:
        raise HTTPException(401, 'Session revoked or expired')
