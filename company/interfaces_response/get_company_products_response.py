from typing import List

from product_card.intarface_response import GetProductCardResponse
from utils.base_model_response import BaseModelResponse


class GetAllCompanyProductsResponse(BaseModelResponse):
    products: List[GetProductCardResponse]
