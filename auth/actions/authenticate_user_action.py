from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
from auth.actions.get_user_by_email_for_auth_action import get_user_by_email_for_auth
from utils.hashing import Hasher
from db.user_model import UserDB

async def authenticate_user(
    email: str, password: str, db: AsyncSession
) -> Union[UserDB, None]:
    user = await get_user_by_email_for_auth(email=email, session=db)
    if user is None:
        return
    if not Hasher.verify_password(password, user.hashed_password):
        return
    return user