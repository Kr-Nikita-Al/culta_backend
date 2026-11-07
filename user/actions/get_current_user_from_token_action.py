from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

import settings
from db.session import get_db
from user.model_dal import UserDAL

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/token")


async def __get_user_by_email_for_auth(email: str, session: AsyncSession):
    async with session.begin():
        user_dal = UserDAL(session)
        return await user_dal.get_user_by_email(
            email=email,
        )


async def __get_user_from_token(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    if 'uid' in payload:
        from uuid import UUID
        from sqlalchemy import select
        from db import UserDB
        try:
            user_id = UUID(payload['uid'])
        except (ValueError, TypeError, AttributeError):
            raise credentials_exception
        async with db.begin():
            user = await db.scalar(select(UserDB).where(UserDB.user_id == user_id))
    else:
        user = await __get_user_by_email_for_auth(email=email, session=db)
    if user is None:
        raise credentials_exception
    from user.account_status import require_confirmed
    require_confirmed(user)
    from auth.session_validation import require_live_session
    await require_live_session(db, user, payload)
    return user
