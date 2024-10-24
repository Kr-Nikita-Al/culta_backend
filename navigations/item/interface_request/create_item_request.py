from typing import Optional

from pydantic import BaseModel, constr, conint


class CreateItemRequest(BaseModel):
    product_card_id: constr()
    item_row_order: Optional[conint()]
    item_column_order: Optional[conint()]
    item_type: Optional[constr()]

