from typing import List, Union

from order.interface_response import GetClientOrderResponse, GetStaffOrderResponse
from utils.base_model_response import BaseModelResponse


class GetClientOrdersResponse(BaseModelResponse):
    orders: List[GetClientOrderResponse]


class GetStaffOrdersResponse(BaseModelResponse):
    orders: List[GetStaffOrderResponse]


GetOrdersResponse = Union[GetStaffOrdersResponse, GetClientOrdersResponse]