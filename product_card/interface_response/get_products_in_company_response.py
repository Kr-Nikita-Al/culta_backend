from typing import List

from product_card.interface_response import GetProductCardResponse
from utils.base_model_response import BaseModelResponse


class GetProductsInCompanyResponse(BaseModelResponse):
    products: List[GetProductCardResponse]
