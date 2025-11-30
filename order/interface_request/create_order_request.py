from typing import Optional, List
from uuid import UUID
from fastapi import HTTPException

from pydantic import BaseModel, constr, conint, validator


class OrderProductItem(BaseModel):
    product_card_id: UUID
    quantity: conint()

    @validator("quantity")
    def validate_quantity(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect quantity")
        return value


class CreateOrderRequest(BaseModel):
    company_id: UUID
    user_id: UUID
    comment: Optional[constr()]
    cocking_time: Optional[conint()]
    order_items: Optional[List[OrderProductItem]]

    @validator("cocking_time")
    def validate_cocking_time(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect cocking_time")
        return value
