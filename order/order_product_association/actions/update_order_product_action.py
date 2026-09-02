from typing import Union, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from order.order_product_association.model_dal import OrderProductAssociationDal


async def __update_order_product_action(order_id: UUID, product_card_id: UUID,
                                        update_order_product_params: Dict,
                                        session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        order_product_dal = OrderProductAssociationDal(session)
        update_order_product_id = await order_product_dal.update_order_product(
            order_id=order_id, product_card_id=product_card_id, **update_order_product_params
        )
        return update_order_product_id

