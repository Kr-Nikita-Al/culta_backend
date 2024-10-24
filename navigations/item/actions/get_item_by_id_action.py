from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ItemDB
from navigations.item.model_dal import ItemDal


async def __get_item_by_id(item_id: UUID, session: AsyncSession) -> Union[ItemDB, None]:
    async with session.begin():
        item_dal = ItemDal(session)
        item = await item_dal.get_item_by_id(
            item_id=item_id
        )
        return item
