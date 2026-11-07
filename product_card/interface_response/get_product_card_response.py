from utils.money import MoneyResponse, PercentageResponse
from datetime import datetime
from typing import Union
from uuid import UUID

from utils.base_model_response import BaseModelResponse


class GetBaseProductCardResponse(BaseModelResponse):
    version: int = 1
    is_used: bool = False
    product_card_id: UUID
    company_id: UUID
    title: str
    sub_title: str
    header: str
    description: str
    hint_header: str
    hint_description: str
    product_category: str
    custom_product_category: str
    allergens_list: str
    quantity_system: str
    tags: str
    bonuses_payment: bool
    single_product_type: bool
    is_sharpness: bool
    is_hotness: bool
    is_active: bool
    count_number: int
    price: MoneyResponse
    cashback_perc: PercentageResponse
    product_quantity: int
    calorie_content: int
    proteins: int
    fats: int
    carbohydrates: int
    cooking_time: int
    company_group_id: int
    image_product_id: UUID
    image_icon_id: UUID

    @classmethod
    def from_orm(cls, product_card):
        data = {c.name: getattr(product_card, c.name)
                for c in product_card.__table__.columns}
        data['is_used'] = bool(product_card.is_used)
        return cls(**data)


class GetClientProductCardResponse(GetBaseProductCardResponse):
    """Ответ для клиента"""


class GetStaffProductCardResponse(GetBaseProductCardResponse):
    """Ответ для сотрудника"""
    product_release_type: str
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime


class GetManagementProductCardResponse(GetStaffProductCardResponse):
    """Financial fields are reserved for company owner/admin."""
    cost_price: MoneyResponse


GetProductCardResponse = Union[GetManagementProductCardResponse, GetStaffProductCardResponse, GetClientProductCardResponse]
