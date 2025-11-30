from uuid import UUID
from fastapi import HTTPException

from pydantic import BaseModel, conint, validator


class CreateOrderProductRequest(BaseModel):
    order_id: UUID
    product_card_id: UUID
    quantity: conint()

    @validator("quantity")
    def validate_quantity(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect quantity")
        return value
