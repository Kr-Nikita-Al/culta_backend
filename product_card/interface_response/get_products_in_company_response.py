from typing import List, Union

from product_card.interface_response import GetClientProductCardResponse, GetStaffProductCardResponse
from utils.base_model_response import BaseModelResponse
from .get_product_card_response import GetManagementProductCardResponse


class GetClientProductsInCompanyResponse(BaseModelResponse):
    products: List[GetClientProductCardResponse]


class GetStaffProductsInCompanyResponse(BaseModelResponse):
    products: List[GetStaffProductCardResponse]


class GetManagementProductsInCompanyResponse(BaseModelResponse):
    products: List[GetManagementProductCardResponse]


GetProductsInCompanyResponse = Union[GetManagementProductsInCompanyResponse, GetStaffProductsInCompanyResponse, GetClientProductsInCompanyResponse]
