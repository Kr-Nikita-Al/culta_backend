from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint


class CreateItemRequest(BaseModel):
    product_card_id: UUID
    container_id: UUID
    item_row_order: Optional[conint()]
    item_column_order: Optional[conint()]
    item_type: Optional[constr()]

