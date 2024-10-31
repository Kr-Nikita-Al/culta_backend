from typing import List
from uuid import UUID
from datetime import datetime, time
from pydantic import EmailStr

from image.interface_response import GetImageResponse
from navigations.screen.interface_response import GetScreenResponse
from utils.base_model_response import BaseModelResponse


class GetScreenIDResponse(BaseModelResponse):
    screen_id: UUID


class GetCompanyResponse(BaseModelResponse):
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
    screens: List[GetScreenIDResponse]
    images: List[GetImageResponse]
