from typing import Union, Optional
from uuid import UUID

from product_card.interface_response import GetClientProductCardResponse, GetStaffProductCardResponse
from utils.base_model_response import BaseModelResponse
from utils.money import MoneyResponse
from product_card.interface_response.get_product_card_response import GetManagementProductCardResponse


def position_data(item, product_model):
    data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
    data['snapshot_available'] = item.unit_price is not None
    if item.product_info is not None:
        product = {name: getattr(item.product_info, name) for name in product_model.__fields__}
        if data['snapshot_available']:
            # Keep older API consumers consistent with the explicit snapshot.
            product.update(title=item.product_title, price=item.unit_price)
            if 'cost_price' in product:
                product['cost_price'] = item.unit_cost_price
        data['product_info'] = product_model(**product)
    return data


class GetBaseOrderProductResponse(BaseModelResponse):
    id: UUID
    order_id: UUID
    product_card_id: UUID
    quantity: int
    product_title: Optional[str] = None
    unit_price: Optional[MoneyResponse] = None
    line_total: Optional[MoneyResponse] = None
    snapshot_available: bool = False


class GetClientOrderProductResponse(GetBaseOrderProductResponse):
    """Ответ для клиента"""
    product_info: GetClientProductCardResponse

    @classmethod
    def from_orm(cls, item):
        return cls(**position_data(item, GetClientProductCardResponse))


class GetStaffOrderProductResponse(GetBaseOrderProductResponse):
    """Ответ для сотрудника"""
    product_info: GetStaffProductCardResponse

    @classmethod
    def from_orm(cls, item):
        return cls(**position_data(item, GetStaffProductCardResponse))


# Универсальный тип для возврата
class GetManagementOrderProductResponse(GetStaffOrderProductResponse):
    product_info: GetManagementProductCardResponse
    unit_cost_price: Optional[MoneyResponse] = None

    @classmethod
    def from_orm(cls, item):
        return cls(**position_data(item, GetManagementProductCardResponse))


GetOrderProductResponse = Union[GetManagementOrderProductResponse, GetStaffOrderProductResponse, GetClientOrderProductResponse]
