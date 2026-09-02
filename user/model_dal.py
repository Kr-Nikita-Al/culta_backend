from typing import Union, List, Tuple
from uuid import UUID

from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import UserRoleDB
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

    async def get_user_staff(self, company_id: UUID) -> Union[List[UserDB], None]:
        query = (
            select(UserDB)
            .options(selectinload(UserDB.roles))
            .join(UserRoleDB, UserDB.user_id == UserRoleDB.user_id)
            .where(UserRoleDB.company_id == company_id)
            .where(UserRoleDB.is_active.is_(True))
            .distinct()
        )
        res = await self.db_session.execute(query)
        users = res.scalars().all()
        return users

    async def get_recent_users(self) -> List[UserDB]:
        """
        Получает последних зарегистрированных пользователей
        """
        query = (
            select(UserDB)
            .options(selectinload(UserDB.roles))  # Загружаем роли
            .order_by(UserDB.time_created.desc())
            .limit(100)
        )
        res = await self.db_session.execute(query)
        return res.scalars().all()

    async def search_users_by_name_or_id(self, search_term: str) -> List[UserDB]:
        """
        Ищет пользователей по имени или user_id
        """
        conditions = []
        # Если search_term можно преобразовать в UUID
        try:
            search_uuid = UUID(search_term)
            conditions.append(UserDB.user_id == search_uuid)
        except ValueError:
            pass
        # Поиск по имени (регистронезависимый)
        conditions.append(UserDB.name.ilike(f"%{search_term}%"))
        query = (
            select(UserDB)
            .options(selectinload(UserDB.roles))  # Загружаем роли
            .where(or_(*conditions))
            .order_by(UserDB.time_created.desc())
            .limit(100)
        )
        res = await self.db_session.execute(query)
        return res.scalars().all()

    async def get_total_users_count(self) -> int:
        """Общее количество пользователей ВО ВСЕЙ СИСТЕМЕ"""
        query = select(func.count()).select_from(UserDB)
        result = await self.db_session.execute(query)
        return result.scalar() or 0

    async def get_users_paginated(self, company_id: UUID = None,
                                  search_term: str = None,
                                  page: int = 1,  # ← Теперь принимаем page вместо offset
                                  page_size: int = 100) -> Tuple[List[UserDB], int, int]:
        """
        Возвращает:
        - users: список пользователей для текущей страницы
        - total_filtered: количество пользователей после фильтрации
        - total_users: общее количество пользователей в системе
        """
        # Вычисляем offset
        offset = (page - 1) * page_size

        # Базовый запрос для данных
        query = select(UserDB).options(selectinload(UserDB.roles))

        # Подсчет отфильтрованных пользователей
        count_query = select(func.count()).select_from(UserDB)

        # Применяем фильтры
        where_conditions = []
        search_conditions = []

        # Фильтр по компании
        if company_id:
            subquery = (
                select(UserRoleDB.user_id)
                .where(
                    and_(
                        UserRoleDB.company_id == company_id,
                        UserRoleDB.is_active.is_(True)
                    )
                )
                .distinct()
                .subquery()
            )
            query = query.join(subquery, UserDB.user_id == subquery.c.user_id)
            count_query = count_query.join(subquery, UserDB.user_id == subquery.c.user_id)

        # Фильтр по поиску
        if search_term:
            # Поиск по user_id
            try:
                search_uuid = UUID(search_term)
                search_conditions.append(UserDB.user_id == search_uuid)
            except ValueError:
                pass
            # Поиск по имени
            search_conditions.append(UserDB.name.ilike(f"%{search_term}%"))
            where_conditions.append(or_(*search_conditions))

        # Применяем WHERE условия
        if where_conditions:
            query = query.where(and_(*where_conditions))
            count_query = count_query.where(and_(*where_conditions))

        # Сортировка
        if company_id:
            query = query.order_by(UserDB.name.asc())
        else:
            query = query.order_by(UserDB.create_date.desc())

        # Пагинация
        query = query.offset(offset).limit(page_size)

        # Выполняем запросы
        res = await self.db_session.execute(query)
        users = res.scalars().all()

        count_res = await self.db_session.execute(count_query)
        total_filtered = count_res.scalar() or 0

        # Получаем общее количество пользователей в системе
        total_users = await self.get_total_users_count()

        return users, total_filtered, total_users
