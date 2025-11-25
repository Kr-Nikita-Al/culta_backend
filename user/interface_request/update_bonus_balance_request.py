from uuid import UUID

from pydantic import BaseModel, StrictBool, StrictFloat


class UpdateBonusBalanceRequest(BaseModel):
    company_id: UUID
    amount: StrictFloat
    is_write_off: StrictBool


