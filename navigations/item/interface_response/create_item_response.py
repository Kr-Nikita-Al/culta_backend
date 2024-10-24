from uuid import UUID
from utils.base_model_response import BaseModelResponse


class CreateItemResponse(BaseModelResponse):
    item_id: UUID
    product_card_id: UUID
    item_row_order: int
    item_column_order: int
    item_type: str
