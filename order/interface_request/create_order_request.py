from typing import Optional
from uuid import UUID
from fastapi import HTTPException

from pydantic import BaseModel, constr, conint, validator


class CreateOrderRequest(BaseModel):
    company_id: UUID
    user_id: UUID
    comment: Optional[constr()]
    cocking_time: Optional[conint()]

    @validator("cocking_time")
    def validate_cocking_time(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect cocking_time")
        return value
