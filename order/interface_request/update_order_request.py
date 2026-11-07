from typing import Optional, List
from pydantic import BaseModel, constr, conint

from order.interface_request.create_order_request import OrderProductItem


class UpdateOrderRequest(BaseModel):
    comment: Optional[constr(max_length=500)] = None
    cocking_time: Optional[conint(ge=0)] = None
    order_items: Optional[List[OrderProductItem]] = None

    class Config:
        extra = 'forbid'
