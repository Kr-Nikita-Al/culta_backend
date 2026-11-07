from utils.money import PercentageResponse
from utils.service_type import ServiceType
from datetime import datetime, time
from uuid import UUID

from pydantic import EmailStr

from utils.base_model_response import BaseModelResponse


class CreateCompanyResponse(BaseModelResponse):
    service_type: ServiceType = ServiceType.SELF_SERVICE
    company_id: UUID
    company_name: str
    address: str
    phone: str
    email: EmailStr
    order_number: int
    city: str
    region: str
    basic_screen_id: UUID
    group_id: int
    image_picture_id: UUID
    image_icon_id: UUID
    bonus_accrual_perc: PercentageResponse
    bonus_payment_perc: PercentageResponse
    is_can_client_create_order: bool
    allow_client_orders_inside: bool = False
    allow_client_orders_outside: bool = False
    is_active: bool
    age_limit: bool
    work_state: bool
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
    start_time: time
    over_time: time
