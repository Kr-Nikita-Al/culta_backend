from typing import Union
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import select, and_, update, delete

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import ContainerDB, ItemDB
from navigations.item.model_dal import ItemDal


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

    async def delete_container(self, container_id: UUID) -> UUID:
        container = await self.get_container_by_id(container_id)
        item_list = [item.item_id for item in container.items]

        # drop items
        if len(item_list) > 0:
            item_dal = ItemDal(self.db_session)
            for item_id in item_list:
                _ = await item_dal.delete_item(
                    item_id=item_id
                )
        query = delete(ContainerDB).where(ContainerDB.container_id == container_id)
        await self.db_session.execute(query)
        return container_id

    async def update_container(self, container_id: UUID, **kwargs) -> Union[UUID, None]:
        query = update(ContainerDB).where(ContainerDB.container_id == container_id)\
                                   .values(kwargs)\
                                   .returning(ContainerDB.container_id)
        res = await self.db_session.execute(query)
        update_container_id_row = res.fetchone()
        if update_container_id_row is not None:
            return update_container_id_row[0]
        return None

