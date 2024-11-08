from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.actions.get_user_by_email_for_auth_action import get_user_by_email_for_auth
from hashing import Hasher
from User.db.model_db import UserDB

async def authenticate_user(
    email: str, password: str, db: AsyncSession
) -> Union[UserDB, None]:
    user = await get_user_by_email_for_auth(email=email, session=db)
    if user is None:
        return
    if not Hasher.verify_password(password, user.hashed_password):
        return
    return user