"""Read-only access token validation; never renews a session."""
import time
from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, HTTPException, Response
from jose import jwt, JWTError
from pydantic import BaseModel
import settings
from user.actions.get_current_user_from_token_action import oauth2_scheme, __get_user_from_token


class TokenStatus(BaseModel):
    valid: bool
    user_id: UUID
    expires_at: datetime
    expires_in: int


async def token_status(response: Response, token: str = Depends(oauth2_scheme),
                       user=Depends(__get_user_from_token)):
    # Reuse the normal account checks and independently require an expiry claim.
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                             options={'require_exp': True, 'require_sub': True})
        expiry = payload['exp']
        if isinstance(expiry, bool) or not isinstance(expiry, int) or expiry <= time.time():
            raise ValueError('Invalid expiry')
        expires_at = datetime.fromtimestamp(expiry, timezone.utc)
    except (JWTError, ValueError, OverflowError, OSError):
        raise HTTPException(401, 'Could not validate credentials', headers={'WWW-Authenticate': 'Bearer'})
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return TokenStatus(valid=True, user_id=user.user_id, expires_at=expires_at,
                       expires_in=max(0, int(expiry - time.time())))
