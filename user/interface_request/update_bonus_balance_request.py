from utils.money import Money
from uuid import UUID

from pydantic import BaseModel, StrictBool, constr, validator


class UpdateBonusBalanceRequest(BaseModel):
    request_id: UUID
    reason: constr(strip_whitespace=True, min_length=1, max_length=500)
    company_id: UUID
    amount: Money
    is_write_off: StrictBool

    @validator('amount')
    def positive_amount(cls, value):
        if value <= 0:
            raise ValueError('Amount must be positive')
        return value

    class Config:
        extra = 'forbid'
