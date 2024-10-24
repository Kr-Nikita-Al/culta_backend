from uuid import UUID

from pydantic import BaseModel


class DeleteProductCardResponse(BaseModel):
    deleted_product_card_id: UUID
