from typing import List, Union

from product_card.interface_response import GetClientProductCardResponse, GetStaffProductCardResponse
from utils.base_model_response import BaseModelResponse


class GetClientProductsInCompanyResponse(BaseModelResponse):
    products: List[GetClientProductCardResponse]


class GetStaffProductsInCompanyResponse(BaseModelResponse):
    products: List[GetStaffProductCardResponse]


GetProductsInCompanyResponse = Union[GetStaffProductsInCompanyResponse, GetClientProductsInCompanyResponse]