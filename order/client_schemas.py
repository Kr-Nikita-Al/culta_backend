from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, conlist, constr, root_validator, validator
from order.interface_request.create_order_request import CreateOrderProductItem
from utils.base_model_response import BaseModelResponse
from utils.money import MoneyResponse
from datetime import datetime
from db import STATUS_TYPE


class ClientOrderResponse(BaseModelResponse):
    order_id: UUID
    check_id: UUID
    company_id: UUID
    user_id: UUID
    price: MoneyResponse
    status: STATUS_TYPE
    order_context: Optional[str] = None
    table_id: Optional[UUID] = None
    time_created: datetime
    replayed: bool = False


class ClientItem(CreateOrderProductItem):
    class Config:
        extra = 'forbid'


class ClientOrderRequest(BaseModel):
    company_id: UUID
    request_id: UUID
    context: Literal['inside', 'outside']
    table_token: Optional[constr(min_length=60, max_length=200)] = None
    check_id: Optional[UUID] = None
    comment: constr(max_length=500) = ''
    order_items: conlist(ClientItem, min_items=1, max_items=100)

    @root_validator(skip_on_failure=True)
    def context_token(cls, values):
        if (values['context'] == 'inside') != (values.get('table_token') is not None):
            raise ValueError('Only inside orders require a table token')
        return values

    @validator('order_items')
    def unique_products(cls, items):
        if len({item.product_card_id for item in items}) != len(items):
            raise ValueError('Each product must appear once')
        return items

    class Config:
        extra = 'forbid'


class TableQRRequest(BaseModel):
    company_id: UUID
    table_id: UUID

    class Config:
        extra = 'forbid'


class ResolveTableRequest(BaseModel):
    company_id: UUID
    table_token: constr(min_length=60, max_length=200)

    class Config:
        extra = 'forbid'
