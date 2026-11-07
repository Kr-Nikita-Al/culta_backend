from utils.money import Percentage
from utils.service_type import ServiceType
from datetime import time
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr, conint, StrictBool

from utils import LETTER_MATCH_PATTERN_PHONE


class UpdateCompanyRequest(BaseModel):
    class Config:
        extra = 'forbid'

    service_type: Optional[ServiceType] = None
    company_name: Optional[constr(min_length=1, max_length=20)]
    address: Optional[constr(min_length=1, max_length=50)]
    phone: Optional[constr()]
    email: Optional[EmailStr]
    order_number: Optional[conint()]
    city: Optional[constr()]
    region: Optional[constr()]
    basic_screen_id: Optional[UUID]
    company_group_id: Optional[conint()]
    image_picture_id: Optional[UUID]
    image_icon_id: Optional[UUID]
    age_limit: Optional[StrictBool]
    work_state: Optional[StrictBool]
    is_can_client_create_order: Optional[StrictBool]
    allow_client_orders_inside: Optional[StrictBool] = None
    allow_client_orders_outside: Optional[StrictBool] = None
    bonus_payment_perc: Optional[Percentage]
    bonus_accrual_perc: Optional[Percentage]
    start_time: Optional[time]
    over_time: Optional[time]

    @validator("phone")
    def validate_name(cls, value):
        if not LETTER_MATCH_PATTERN_PHONE.match(value):
            raise HTTPException(
                status_code=422, detail="Incorrect phone"
            )
        return value
