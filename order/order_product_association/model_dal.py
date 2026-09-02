from typing import Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

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

    async def update_order_product(self, order_id: UUID, product_card_id: UUID, **kwargs) -> Union[UUID, None]:
        query = update(OrderProductAssociationDB).where(and_(OrderProductAssociationDB.order_id == order_id,
                                                             OrderProductAssociationDB.product_card_id == product_card_id)) \
            .values(kwargs) \
            .returning(OrderProductAssociationDB.id)
        res = await self.db_session.execute(query)
        update_order_product_id_row = res.unique().fetchone()
        if update_order_product_id_row is not None:
            return update_order_product_id_row[0]
        return None
