from sqlalchemy.ext.asyncio import AsyncSession

from navigations.item.interface_request import CreateItemRequest
from navigations.item.interface_response import CreateItemResponse
from navigations.item.model_dal import ItemDal


async def __create_item(item_body: CreateItemRequest, session: AsyncSession) -> CreateItemResponse:
    async with session.begin():
        item_dal = ItemDal(session)
        item_db = await item_dal.create_item(
            item_body.__dict__
        )
        return CreateItemResponse(
            item_id=item_db.item_id,
            container_id=item_db.container_id,
            product_card_id=item_db.product_card_id,
            item_row_order=item_db.item_row_order,
            item_column_order=item_db.item_column_order,
            item_type=item_db.item_type,
        )
