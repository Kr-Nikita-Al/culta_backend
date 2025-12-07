from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, constr, conint, validator


class CreateItemRequest(BaseModel):
    product_card_id: UUID
    container_id: UUID
    item_row_order: Optional[conint()]
    item_column_order: Optional[conint()]
    item_type: Optional[constr()]

    @validator("item_column_order")
    def validate_item_column_order(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect item_column_order")
        return value

    @validator("item_row_order")
    def validate_item_row_order(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect item_row_order")
        return value
