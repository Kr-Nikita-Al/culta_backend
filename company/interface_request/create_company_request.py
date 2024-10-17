from datetime import time

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr, conint, StrictBool

from utils import LETTER_MATCH_PATTERN_PHONE


class CreateCompanyRequest(BaseModel):
    company_name: constr(min_length=1, max_length=20)
    address: constr(min_length=1, max_length=50)
    phone: constr()
    email: EmailStr
    order_number: conint()
    main_screen_id: conint()
    group_id: conint()
    company_image: constr()
    company_icon: constr()
    age_limit: StrictBool
    work_state: StrictBool
    start_time: time
    over_time: time

    @validator("phone")
    def validate_name(cls, value):
        if not LETTER_MATCH_PATTERN_PHONE.match(value):
            raise HTTPException(
                status_code=422, detail="Incorrect phone"
            )
        return value