from uuid import UUID
from decimal import Decimal
from utils.money import CENT, MAX_MONEY

from fastapi import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from order.interface_request import CreateOrderRequest
from order.interface_response import CreateOrderResponse
from order.model_dal import OrderDal
from order.order_product_association.model_dal import OrderProductAssociationDal
from order.order_product_association.snapshot import capture_snapshot
from checks.service import assign_check


async def __create_order(order_body: CreateOrderRequest, user_id: UUID, session: AsyncSession, *, client_request=None) -> CreateOrderResponse:
    async with session.begin():
        context = None
        if client_request is not None:
            from order.client_service import prepare_client_order
            previous, context = await prepare_client_order(session, client_request, user_id)
            if previous is not None:
                return CreateOrderResponse.from_orm(previous).copy(update={'replayed': True})
        if context is None:
            check_id = await assign_check(session, order_body, user_id)
        else:
            check_id = await assign_check(session, order_body, user_id, client_context=context)
        order_dal = OrderDal(session)
        order_db = await order_dal.create_order(
            {**order_body.__dict__, **(context or {}), 'check_id': check_id}, creator_user_id=user_id
        )
        positions = OrderProductAssociationDal(session)
        total = Decimal('0')
        for item in order_body.order_items or []:
            snapshot = await capture_snapshot(session, order_body.company_id,
                                              item.product_card_id, item.quantity)
            await positions.create_order_product({
                'order_id': order_db.order_id,
                'product_card_id': item.product_card_id,
                'quantity': item.quantity,
                **snapshot,
            })
            total += snapshot['line_total']
        if total > MAX_MONEY:
            raise HTTPException(422, 'Order total exceeds the supported amount')
        order_db.price = total.quantize(CENT)
        order_db.check_id = check_id
        await session.flush()
        return CreateOrderResponse(
            order_context=getattr(order_db, 'order_context', None),
            table_id=getattr(order_db, 'table_id', None),
            check_id=check_id,
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
            price=order_db.price,
        )
