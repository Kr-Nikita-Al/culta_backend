from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, constr, conint
from utils.order_quantity import CreateQuantity


class OrderProductItem(BaseModel):
    product_card_id: UUID
    quantity: conint(ge=0)


class CreateOrderProductItem(OrderProductItem):
    quantity: CreateQuantity


class CreateOrderRequest(BaseModel):
    check_id: Optional[UUID] = None
    company_id: UUID
    user_id: Optional[UUID] = None
    guest_name: Optional[constr(strip_whitespace=True, max_length=100)] = None
    table_id: Optional[UUID] = None
    comment: Optional[constr(max_length=500)] = None
    cocking_time: Optional[conint(ge=0)] = None
    order_items: Optional[List[CreateOrderProductItem]] = None

    class Config:
        extra = 'forbid'
