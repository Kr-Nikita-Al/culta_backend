from uuid import UUID

from pydantic import BaseModel


class UpdateProductResponse(BaseModel):
    updated_product_card_id: UUID
