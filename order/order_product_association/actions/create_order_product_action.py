from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from db import OrderDB, STATUS_TYPE

from order.order_product_association.interface_request import CreateOrderProductRequest
from order.order_product_association.interface_response import CreateOrderProductResponse
from order.order_product_association.model_dal import OrderProductAssociationDal
from order.order_product_association.snapshot import capture_snapshot
from order.model_dal import OrderDal


async def __create_order_product_action(order_body: CreateOrderProductRequest,
                                        session: AsyncSession) -> CreateOrderProductResponse:
    async with session.begin():
        result = await session.execute(select(OrderDB).where(OrderDB.order_id == order_body.order_id).with_for_update())
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(404, 'Order not found')
        if order.status in (STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED):
            raise HTTPException(409, 'Order is closed or canceled')
        snapshot = await capture_snapshot(session, order.company_id,
                                          order_body.product_card_id, order_body.quantity)
        order_product_dal = OrderProductAssociationDal(session)
        order_product_db = await order_product_dal.create_order_product(
            {**order_body.__dict__, **snapshot}
        )
        total = await order_product_dal.calculate_order_total(order.order_id)
        if await OrderDal(session).update_order(order.order_id, price=total) is None:
            raise HTTPException(409, 'Order changed; reload and retry')
        return CreateOrderProductResponse(
            id=order_product_db.id,
            order_id=order_product_db.order_id,
            product_card_id=order_product_db.product_card_id,
            quantity=order_product_db.quantity,
        )
