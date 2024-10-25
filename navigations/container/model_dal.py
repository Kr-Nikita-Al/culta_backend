from typing import Union
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import select, and_, update, delete

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import ContainerDB, ItemDB


class ContainerDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_container(self, kwargs) -> ContainerDB:
        # check existing screen by screen_id
        new_container = ContainerDB(
            container_title=kwargs["container_title"],
            container_sub_title=kwargs["container_sub_title"],
            container_type=kwargs["container_type"],
            container_order=kwargs["container_order"],
        )
        self.db_session.add(new_container)
        await self.db_session.flush()
        return new_container

    async def get_container_by_id(self, container_id: UUID) -> Union[ContainerDB, None]:
        query = select(ContainerDB).where(ContainerDB.container_id == container_id).options(joinedload(ContainerDB.items))
        res = await self.db_session.execute(query)
        container_row = res.scalars().first()
        if container_row is not None:
            return container_row
        return None

    # async def delete_company(self, item_id: UUID) -> Union[ItemDB, None]:
    #     query = delete(ItemDB).where(ItemDB.item_id == item_id)
    #     await self.db_session.execute(query)
    #     return item_id
    #
    # async def update_item(self, item_id: UUID, **kwargs) -> Union[UUID, None]:
    #     query = update(ItemDB).where(ItemDB.item_id == item_id)\
    #                           .values(kwargs)\
    #                           .returning(ItemDB.item_id)
    #     res = await self.db_session.execute(query)
    #     update_item_id_row = res.fetchone()
    #     if update_item_id_row is not None:
    #         return update_item_id_row[0]
    #     return None

