from uuid import UUID

from pydantic import BaseModel


class UpdateOrderResponse(BaseModel):
    updated_order_id: UUID
