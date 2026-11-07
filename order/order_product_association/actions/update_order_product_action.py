from typing import Union, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from db import STATUS_TYPE
from order.model_dal import OrderDal

from order.order_product_association.model_dal import OrderProductAssociationDal


async def __update_order_product_action(order_id: UUID, product_card_id: UUID,
                                        update_order_product_params: Dict,
                                        session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        orders = OrderDal(session)
        status = await orders.get_order_status_for_update(order_id)
        if status is None:
            raise HTTPException(404, 'Order not found')
        if status in (STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED):
            raise HTTPException(409, 'Order is closed or canceled')
        order_product_dal = OrderProductAssociationDal(session)
        update_order_product_id = await order_product_dal.update_order_product(
            order_id=order_id, product_card_id=product_card_id, **update_order_product_params
        )
        if update_order_product_id is not None:
            total = await order_product_dal.calculate_order_total(order_id)
            if await orders.update_order(order_id, price=total) is None:
                raise HTTPException(409, 'Order changed; reload and retry')
        return update_order_product_id
