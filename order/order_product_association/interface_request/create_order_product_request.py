from uuid import UUID
from pydantic import BaseModel
from utils.order_quantity import CreateQuantity


class CreateOrderProductRequest(BaseModel):
    order_id: UUID
    product_card_id: UUID
    quantity: CreateQuantity
