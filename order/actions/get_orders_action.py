from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import STATUS_TYPE
from order.interface_response import GetOrdersResponse, GetStaffOrdersResponse, GetStaffOrderResponse, \
    GetClientOrdersResponse, GetClientOrderResponse
from order.model_dal import OrderDal
from utils.constants import EMPTY_UUID
from order.interface_response.get_order_response import GetManagementOrderResponse
from order.interface_response.get_orders_response import GetManagementOrdersResponse


async def __get_orders(is_staff: bool, session: AsyncSession, user_id: UUID, statuses: List[STATUS_TYPE],
                       company_id: UUID = EMPTY_UUID, include_cost: bool = False) -> GetOrdersResponse:
    async with session.begin():
        order_dal = OrderDal(session)
        if is_staff:
            orders = await order_dal.get_orders_in_company(company_id=company_id, statuses=statuses)
        else:
            orders = await order_dal.get_user_orders(user_id=user_id, statuses=statuses)
    orders = orders or []
    if is_staff and include_cost:
        return GetManagementOrdersResponse(orders=[GetManagementOrderResponse.from_orm(order) for order in orders])
    if is_staff:
        orders = [GetStaffOrderResponse.from_orm(order) for order in orders]
        return GetStaffOrdersResponse(orders=orders)
    orders = [GetClientOrderResponse.from_orm(order) for order in orders]
    return GetClientOrdersResponse(orders=orders)
