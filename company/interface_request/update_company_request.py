from datetime import time
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr, conint, StrictBool

from utils import LETTER_MATCH_PATTERN_PHONE


class UpdateCompanyRequest(BaseModel):
    company_name: Optional[constr(min_length=1, max_length=20)]
    address: Optional[constr(min_length=1, max_length=50)]
    phone: Optional[constr()]
    email: Optional[EmailStr]
    order_number: Optional[conint()]
    main_screen_id: Optional[conint()]
    company_group_id: Optional[conint()]
    company_image: Optional[constr()]
    company_icon: Optional[constr()]
    age_limit: Optional[StrictBool]
    work_state: Optional[StrictBool]
    start_time: Optional[time]
    over_time: Optional[time]

    @validator("phone")
    def validate_name(cls, value):
        if not LETTER_MATCH_PATTERN_PHONE.match(value):
            raise HTTPException(
                status_code=422, detail="Incorrect phone"
            )
        return value
