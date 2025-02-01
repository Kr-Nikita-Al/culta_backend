from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.item.model_dal import ItemDal


async def __check_item_positions(session: AsyncSession, row_order: int, column_order: int, container_id: UUID) -> bool:
    async with session.begin():
        item_dal = ItemDal(session)
        items = await item_dal.get_all_items()
        if items is not None:
            list_row_orders = [item.item_row_order for item in items if item.container_id == container_id]
            list_column_orders = [item.item_column_order for item in items if item.container_id == container_id]
            return not(row_order in list_row_orders and column_order in list_column_orders) and row_order >= 0 and column_order >= 0
        return True
