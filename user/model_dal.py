from typing import Union
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.user_model import UserDB
from fastapi import HTTPException


class UserDAL:
    """Data Access Layer for operating user info"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_user(self, name: str, surname: str, phone: str,
                          email: str, hashed_password: str) -> UserDB:
        if await self.get_user_by_email(email):
            raise HTTPException(status_code=404,
                                detail='User with email {0} already exists'.format(email))
        new_user = UserDB(
            name=name,
            surname=surname,
            phone=phone,
            email=email,
            hashed_password=hashed_password,
        )
        self.db_session.add(new_user)
        await self.db_session.flush()
        return new_user

    async def delete_user(self, user_id: UUID) -> Union[UUID, None]:
        query = (
            update(UserDB)
            .where(and_(UserDB.user_id == user_id, UserDB.is_active == True))
            .values(is_active=False)
            .returning(UserDB.user_id)
        )
        res = await self.db_session.execute(query)
        deleted_user_id_row = res.fetchone()
        if deleted_user_id_row is not None:
            return deleted_user_id_row[0]
        return None

    async def get_user_by_id(self, user_id: UUID) -> Union[UserDB, None]:
        query = select(UserDB).where(UserDB.user_id == user_id)
        res = await self.db_session.execute(query)
        user_row = res.fetchone()
        if user_row is not None:
            return user_row[0]
        return None

    async def get_user_by_email(self, email: str) -> Union[UserDB, None]:
        query = select(UserDB).where(UserDB.email == email)
        res = await self.db_session.execute(query)
        user_row = res.fetchone()
        if user_row is not None:
            return user_row[0]
        return None

    async def update_user(self, user_id: UUID, **kwargs) -> Union[UUID, None]:
        query = (
            update(UserDB)
            .where(and_(UserDB.user_id == user_id, UserDB.is_active == True))
            .values(kwargs)
            .returning(UserDB.user_id)
        )
        res = await self.db_session.execute(query)
        update_user_id_row = res.fetchone()
        if update_user_id_row is not None:
            return update_user_id_row[0]
        return None
