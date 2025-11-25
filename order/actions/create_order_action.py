from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from order.interface_request import CreateOrderRequest
from order.interface_response import CreateOrderResponse
from order.model_dal import OrderDal


async def __create_order(order_body: CreateOrderRequest, user_id: UUID, session: AsyncSession) -> CreateOrderResponse:
    async with session.begin():
        order_dal = OrderDal(session)
        order_db = await order_dal.create_order(
            order_body.__dict__, creator_user_id=user_id
        )
        return CreateOrderResponse(
            order_id=order_db.order_id,
            company_id=order_db.company_id,
            user_id=order_db.user_id,
            staff_id=order_db.staff_id,
            comment=order_db.comment,
            cocking_time=order_db.cocking_time,
            status=order_db.status,
            creator_id=order_db.creator_id,
            updater_id=order_db.updater_id,
            time_created=order_db.time_created,
            time_updated=order_db.time_updated,
        )
