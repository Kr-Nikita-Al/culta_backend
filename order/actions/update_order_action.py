from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from order.model_dal import OrderDal


async def __update_order_by_id(update_order_params: Dict, order_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        order = OrderDal(session)
        updated_order_id = await order.update_order(
            order_id=order_id,
            **update_order_params
        )
        return updated_order_id
