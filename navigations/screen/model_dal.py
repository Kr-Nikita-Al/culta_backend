from typing import Union
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import select, and_, update, delete

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import ScreenDB, CompanyDB
from navigations.container.model_dal import ContainerDal


class ScreenDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_screen(self, kwargs) -> ScreenDB:
        company_id = kwargs["company_id"]
        query = select(CompanyDB).where(and_(CompanyDB.company_id == company_id,
                                             CompanyDB.is_active == True))
        res = await self.db_session.execute(query)
        company_row = res.unique().fetchone()
        if company_row is not None:
            company_id_for_adding = company_row[0].company_id
        else:
            raise HTTPException(status_code=404,
                                detail='Company with id {0} was not exit or deleted before'.format(company_id))
        new_screen = ScreenDB(
            company_id=company_id_for_adding,
            company_group_id=kwargs["company_group_id"],
            screen_title=kwargs["screen_title"],
            screen_sub_title=kwargs["screen_sub_title"],
            screen_count_number=kwargs["screen_count_number"],
        )
        self.db_session.add(new_screen)
        await self.db_session.flush()
        return new_screen

    async def get_screen_by_id(self, screen_id: UUID) -> Union[ScreenDB, None]:
        query = select(ScreenDB).where(ScreenDB.screen_id == screen_id).options(joinedload(ScreenDB.containers))
        res = await self.db_session.execute(query)
        screen_row = res.scalars().first()
        if screen_row is not None:
            return screen_row
        return None

    async def delete_screen(self, screen_id: UUID) -> UUID:
        screen = await self.get_screen_by_id(screen_id)
        container_list = [container.container_id for container in screen.containers]

        # drop items
        if len(container_list) > 0:
            container_dal = ContainerDal(self.db_session)
            for container_id in container_list:
                _ = await container_dal.delete_container(
                    container_id=container_id
                )
        query = delete(ScreenDB).where(ScreenDB.screen_id == screen_id)
        await self.db_session.execute(query)
        return screen_id

    async def update_screen(self, screen_id: UUID, **kwargs) -> Union[UUID, None]:
        query = update(ScreenDB).where(ScreenDB.screen_id == screen_id)\
                                .values(kwargs)\
                                .returning(ScreenDB.screen_id)
        res = await self.db_session.execute(query)
        update_screen_id_row = res.fetchone()
        if update_screen_id_row is not None:
            return update_screen_id_row[0]
        return None

