from utils.money import MoneyResponse
from datetime import datetime
from typing import List, Union, Optional
from uuid import UUID

from db import STATUS_TYPE
from order.order_product_association.interface_response import (GetClientOrderProductResponse,
                                                                GetStaffOrderProductResponse)
from utils.base_model_response import BaseModelResponse
from order.order_product_association.interface_response.get_order_product_response import GetManagementOrderProductResponse


class GetBaseOrderResponse(BaseModelResponse):
    order_context: Optional[str] = None
    table_id: Optional[UUID] = None
    check_id: UUID = None
    check_status: Optional[str] = None
    order_id: UUID
    cocking_time: int
    status: STATUS_TYPE
    company_id: UUID
    user_id: Optional[UUID] = None
    price: MoneyResponse
    bonus_transaction: MoneyResponse
    time_created: datetime


def convert_order_to_response(order, is_staff: bool, include_cost: bool = False):
    """Конвертирует ORM объект заказа в соответствующую модель ответа"""
    if is_staff:
        if include_cost:
            return GetManagementOrderResponse.from_orm(order)
        return GetStaffOrderResponse.from_orm(order)
    return GetClientOrderResponse.from_orm(order)


class GetClientOrderResponse(GetBaseOrderResponse):
    """Ответ для клиента"""
    order_items: List[GetClientOrderProductResponse]

    @classmethod
    def from_orm(cls, order):
        data = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        data['check_status'] = getattr(order.__dict__.get('check_info'), 'status', None)
        # Обрабатываем order_items
        if hasattr(order, 'order_items'):
            data['order_items'] = [
                GetClientOrderProductResponse.from_orm(item)
                for item in order.order_items
            ]
        return cls(**data)


class GetStaffOrderResponse(GetBaseOrderResponse):
    """Ответ для сотрудника"""
    staff_id: UUID
    comment: str
    creator_id: UUID
    updater_id: UUID
    time_updated: datetime
    order_items: List[GetStaffOrderProductResponse]

    @classmethod
    def from_orm(cls, order):
        data = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        data['check_status'] = getattr(order.__dict__.get('check_info'), 'status', None)
        # Обрабатываем order_items
        if hasattr(order, 'order_items'):
            data['order_items'] = [
                GetStaffOrderProductResponse.from_orm(item)
                for item in order.order_items
            ]
        return cls(**data)


# Универсальный тип для возврата
class GetManagementOrderResponse(GetStaffOrderResponse):
    order_items: List[GetManagementOrderProductResponse]

    @classmethod
    def from_orm(cls, order):
        data = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        data['check_status'] = getattr(order.__dict__.get('check_info'), 'status', None)
        data['order_items'] = [GetManagementOrderProductResponse.from_orm(item) for item in order.order_items]
        return cls(**data)


GetOrderResponse = Union[GetManagementOrderResponse, GetStaffOrderResponse, GetClientOrderResponse]
