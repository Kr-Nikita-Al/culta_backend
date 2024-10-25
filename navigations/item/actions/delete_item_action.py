from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.item.model_dal import ItemDal


async def __delete_item(item_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        item_dal = ItemDal(session)
        deleted_item_id = await item_dal.delete_item(
            item_id=item_id
        )
        return deleted_item_id
