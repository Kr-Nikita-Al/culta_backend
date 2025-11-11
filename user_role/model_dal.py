from typing import Union, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.user_role_model import UserRoleDB
from user_role.interface_response import GetUserRolesResponse
from utils.constants import PortalRole


class UserRoleDAL:
    """Data Access Layer for operating user_role info"""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def grant_user_role(self, user_id: UUID, company_id: UUID, role: PortalRole, creator_id: UUID) -> UserRoleDB:
        if await self.is_exist_user_role(user_id, company_id, role):
            raise HTTPException(status_code=400, detail='Role {0} already exist'.format(role))
        new_user_role = UserRoleDB(
            user_id=user_id,
            company_id=company_id,
            role=role,
            creator_id=creator_id,
        )
        self.db_session.add(new_user_role)
        await self.db_session.flush()
        return new_user_role

    async def is_exist_user_role(self, user_id: UUID, company_id: UUID, role: PortalRole):
        query = select(UserRoleDB).where(and_(UserRoleDB.company_id == company_id,
                                              UserRoleDB.user_id == user_id,
                                              UserRoleDB.role == role,
                                              UserRoleDB.is_active == True))
        res = await self.db_session.execute(query)
        user_role_row = res.unique().fetchone()
        return user_role_row is not None

    async def get_user_roles(self, user_id: UUID) -> Union[List[GetUserRolesResponse], None]:
        query = select(UserRoleDB).where(and_(UserRoleDB.user_id == user_id,
                                              UserRoleDB.is_active == True))
        res = await self.db_session.execute(query)
        user_role_row = res.unique().scalars().all()
        if user_role_row is not None:
            return user_role_row
        return None

    async def revoke_user_role(self, user_id: UUID, company_id: UUID, role: PortalRole) -> Union[UUID, None]:
        query = update(UserRoleDB).where(and_(UserRoleDB.user_id == user_id,
                                              UserRoleDB.company_id == company_id,
                                              UserRoleDB.role == role)) \
            .values(is_active=False) \
            .returning(UserRoleDB.user_id)
        res = await self.db_session.execute(query)
        deleted_user_role_id_row = res.unique().fetchone()
        if deleted_user_role_id_row is not None:
            return deleted_user_role_id_row[0]
        return None
