from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from order.interface_response import GetStaffOrderResponse, GetClientOrderResponse
from order.interface_response.get_order_response import convert_order_to_response
from order.model_dal import OrderDal


async def __get_order_by_id(order_id: UUID, is_staff: bool, session: AsyncSession) -> Union[GetStaffOrderResponse,
                                                                                            GetClientOrderResponse,
                                                                                            None]:
    async with session.begin():
        order_dal = OrderDal(session)
        order = await order_dal.get_order_by_id(
            order_id=order_id
        )
    if order is None:
        return order
    return convert_order_to_response(order, is_staff)



