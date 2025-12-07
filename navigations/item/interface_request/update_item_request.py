from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, conint


class UpdateItemRequest(BaseModel):
    item_type: Optional[constr()]
    item_column_order: Optional[conint()]
    item_row_order: Optional[conint()]

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
