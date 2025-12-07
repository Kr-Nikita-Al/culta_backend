from typing import List

from order.interface_response import GetOrderResponse
from utils.base_model_response import BaseModelResponse


class GetAllOrderResponse(BaseModelResponse):
    orders: List[GetOrderResponse]
