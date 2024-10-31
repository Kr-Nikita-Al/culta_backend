from datetime import datetime, time
from uuid import UUID

from pydantic import EmailStr

from utils.base_model_response import BaseModelResponse


class CreateCompanyResponse(BaseModelResponse):
    company_id: UUID
    company_name: str
    address: str
    phone: str
    email: EmailStr
    is_active: bool
    order_number: int
    basic_screen_id: UUID
    group_id: int
    image_picture_id: UUID
    image_icon_id: UUID
    age_limit: bool
    work_state: bool
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
    start_time: time
    over_time: time
