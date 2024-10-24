from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.item.model_dal import ItemDal


async def __update_item_by_id(update_item_params: Dict, item_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        item = ItemDal(session)
        updated_item_id = await item.update_item(
            item_id=item_id,
            **update_item_params
        )
        return updated_item_id
