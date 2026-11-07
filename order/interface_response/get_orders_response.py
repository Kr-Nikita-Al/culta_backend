from typing import List, Union

from order.interface_response import GetClientOrderResponse, GetStaffOrderResponse
from utils.base_model_response import BaseModelResponse
from .get_order_response import GetManagementOrderResponse


class GetClientOrdersResponse(BaseModelResponse):
    orders: List[GetClientOrderResponse]


class GetStaffOrdersResponse(BaseModelResponse):
    orders: List[GetStaffOrderResponse]


class GetManagementOrdersResponse(BaseModelResponse):
    orders: List[GetManagementOrderResponse]


GetOrdersResponse = Union[GetManagementOrdersResponse, GetStaffOrdersResponse, GetClientOrdersResponse]
