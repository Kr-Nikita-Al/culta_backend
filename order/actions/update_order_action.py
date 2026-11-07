from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db import STATUS_TYPE
from order.interface_request.create_order_request import OrderProductItem
from order.model_dal import OrderDal
from order.order_product_association.model_dal import OrderProductAssociationDal


async def __update_order_by_id(update_order_params: Dict, order_id: UUID, session: AsyncSession,
                               order_items: Optional[List[OrderProductItem]] = None,
                               expected_status: Optional[STATUS_TYPE] = None,
                               status_reason: Optional[str] = None) -> UUID:
    async with session.begin():
        order = OrderDal(session)
        # Serialize edits and recheck the status before changing any positions.
        status = await order.get_order_status_for_update(order_id)
        if status is None:
            raise HTTPException(status_code=404, detail='Order not found')
        if status in (STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED):
            raise HTTPException(status_code=409, detail='Order is closed or canceled')
        if expected_status is not None and status != expected_status:
            raise HTTPException(status_code=409, detail='Order changed; reload and retry')

        positions = OrderProductAssociationDal(session)
        for item in order_items or []:
            updated_item_id = await positions.update_order_product(
                order_id=order_id, product_card_id=item.product_card_id, quantity=item.quantity
            )
            if updated_item_id is None:
                raise HTTPException(status_code=404,
                                    detail='Product card with id {0} is not found in order'.format(item.product_card_id))
        update_order_params = dict(update_order_params)
        # Never accept a caller-supplied total, even through an internal action.
        update_order_params.pop('price', None)
        if order_items:
            update_order_params['price'] = await positions.calculate_order_total(order_id)
        updated_order_id = await order.update_order(
            order_id=order_id,
            **update_order_params
        )
        if updated_order_id is None:
            raise HTTPException(status_code=409, detail='Order changed; reload and retry')
        new_status = update_order_params.get('status')
        if new_status is not None and new_status != status:
            await order.append_status_history(order_id, status, new_status,
                                               update_order_params['updater_id'], status_reason)
        return updated_order_id
