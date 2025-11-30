from sqlalchemy.ext.asyncio import AsyncSession

from db import OrderProductAssociationDB


class OrderProductAssociationDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_order_product(self, kwargs) -> OrderProductAssociationDB:
        new_order_product_item = OrderProductAssociationDB(
            order_id=kwargs["order_id"],
            product_card_id=kwargs["product_card_id"],
            quantity=kwargs["quantity"]
        )
        self.db_session.add(new_order_product_item)
        await self.db_session.flush()
        return new_order_product_item
