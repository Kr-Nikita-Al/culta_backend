from typing import Union
from uuid import UUID

from product_card.interface_response import GetClientProductCardResponse, GetStaffProductCardResponse
from utils.base_model_response import BaseModelResponse


class GetBaseOrderProductResponse(BaseModelResponse):
    id: UUID
    order_id: UUID
    product_card_id: UUID
    quantity: int


class GetClientOrderProductResponse(GetBaseOrderProductResponse):
    """Ответ для клиента"""
    product_info: GetClientProductCardResponse

    @classmethod
    def from_orm(cls, item):
        data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
        if hasattr(item, 'product_info') and item.product_info:
            data['product_info'] = GetClientProductCardResponse.from_orm(
                item.product_info
            )
        return cls(**data)


class GetStaffOrderProductResponse(GetBaseOrderProductResponse):
    """Ответ для сотрудника"""
    product_info: GetStaffProductCardResponse

    @classmethod
    def from_orm(cls, item):
        data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
        if hasattr(item, 'product_info') and item.product_info:
            data['product_info'] = GetStaffProductCardResponse.from_orm(
                item.product_info
            )
        return cls(**data)


# Универсальный тип для возврата
GetOrderProductResponse = Union[GetClientOrderProductResponse, GetStaffOrderProductResponse]