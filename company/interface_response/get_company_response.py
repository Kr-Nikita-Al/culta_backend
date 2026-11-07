from pydantic import validator
from utils.money import PercentageResponse
from utils.service_type import ServiceType
from typing import List
from uuid import UUID
from datetime import datetime, time
from pydantic import EmailStr

from image.interface_response import GetImageInterface
from navigations.screen.interface_response import GetScreenResponse
from utils.base_model_response import BaseModelResponse


class GetScreenIDResponse(BaseModelResponse):
    screen_id: UUID


class GetCompanyResponse(BaseModelResponse):
    orders_enabled: bool = True
    reservations_enabled: bool = True
    images_enabled: bool = True
    service_type: ServiceType = ServiceType.SELF_SERVICE
    company_id: UUID
    company_name: str
    address: str
    phone: str
    email: EmailStr
    is_active: bool
    order_number: int
    city: str
    region: str
    basic_screen_id: UUID
    group_id: int
    image_picture_id: UUID
    image_icon_id: UUID
    age_limit: bool
    work_state: bool
    is_can_client_create_order: bool
    allow_client_orders_inside: bool = False
    allow_client_orders_outside: bool = False
    bonus_payment_perc: PercentageResponse
    bonus_accrual_perc: PercentageResponse
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
    start_time: time
    over_time: time
    screens: List[GetScreenIDResponse]

    @validator('screens', pre=True, allow_reuse=True)
    def published_children(cls, values):
        from navigations.publication import published
        return [value for value in values if published(value)]
