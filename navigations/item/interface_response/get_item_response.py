from datetime import datetime
from typing import List
from uuid import UUID

from product_card.interface_response import GetProductCardResponse
from utils.base_model_response import BaseModelResponse


class GetItemResponse(BaseModelResponse):
    item_id: UUID
    product_card_id: UUID
    item_row_order: int
    item_column_order: int
    item_type: str
    product_card_info: GetProductCardResponse
