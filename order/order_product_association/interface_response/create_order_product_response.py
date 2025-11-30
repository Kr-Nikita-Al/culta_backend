from uuid import UUID

from utils.base_model_response import BaseModelResponse


class CreateOrderProductResponse(BaseModelResponse):
    id: UUID
    order_id: UUID
    product_card_id: UUID
    quantity: int
