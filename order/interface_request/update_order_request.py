from typing import Optional, List
from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, conint

from order.interface_request.create_order_request import OrderProductItem


class UpdateOrderRequest(BaseModel):
    comment: Optional[constr()]
    cocking_time: Optional[conint()]
    order_items: Optional[List[OrderProductItem]]

    @validator("cocking_time")
    def validate_cocking_time(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect cocking_time")
        return value
