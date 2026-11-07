from uuid import UUID
from typing import Optional

from product_card.interface_response import GetProductCardResponse
from utils.base_model_response import BaseModelResponse


class GetItemResponse(BaseModelResponse):
    item_id: UUID
    product_card_id: UUID
    container_id: UUID
    item_row_order: int
    item_column_order: int
    item_type: str
    layout_x: Optional[int] = None
    layout_y: Optional[int] = None
    product_card_info: GetProductCardResponse
