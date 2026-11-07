from typing import Union
from decimal import Decimal
from fastapi import HTTPException
from utils.money import MAX_MONEY, CENT
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from db import OrderProductAssociationDB
from order.order_product_association.snapshot import line_total


class OrderProductAssociationDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def calculate_order_total(self, order_id: UUID) -> Decimal:
        # The caller must hold the parent order lock until the total is saved.
        result = await self.db_session.execute(select(
            OrderProductAssociationDB.unit_price, OrderProductAssociationDB.quantity
        ).where(OrderProductAssociationDB.order_id == order_id))
        total = Decimal('0.00')
        for price, quantity in result.all():
            if price is None or quantity is None:
                raise HTTPException(409, 'Order has positions without historical prices; quantities cannot be changed')
            total += line_total(price, quantity)
            if total > MAX_MONEY:
                raise HTTPException(422, 'Order total exceeds the supported amount')
        return total.quantize(CENT)

    async def create_order_product(self, kwargs) -> OrderProductAssociationDB:
        new_order_product_item = OrderProductAssociationDB(
            order_id=kwargs["order_id"],
            product_card_id=kwargs["product_card_id"],
            quantity=kwargs["quantity"],
            product_title=kwargs['product_title'],
            unit_price=kwargs['unit_price'],
            unit_cost_price=kwargs['unit_cost_price'],
            line_total=kwargs['line_total'],
        )
        self.db_session.add(new_order_product_item)
        await self.db_session.flush()
        return new_order_product_item

    async def update_order_product(self, order_id: UUID, product_card_id: UUID, quantity: int) -> Union[UUID, None]:
        result = await self.db_session.execute(
            select(OrderProductAssociationDB).where(
                OrderProductAssociationDB.order_id == order_id,
                OrderProductAssociationDB.product_card_id == product_card_id,
            ).with_for_update()
        )
        position = result.scalar_one_or_none()
        if position is None:
            return None
        # Only quantity and its amount may change; never reread the catalog.
        kwargs = {'quantity': quantity, 'line_total':
                  None if position.unit_price is None else line_total(position.unit_price, quantity)}
        query = update(OrderProductAssociationDB).where(and_(OrderProductAssociationDB.order_id == order_id,
                                                             OrderProductAssociationDB.product_card_id == product_card_id)) \
            .values(kwargs) \
            .returning(OrderProductAssociationDB.id)
        res = await self.db_session.execute(query)
        update_order_product_id_row = res.unique().fetchone()
        if update_order_product_id_row is not None:
            return update_order_product_id_row[0]
        return None
