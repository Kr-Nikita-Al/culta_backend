from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint


class CreateScreenRequest(BaseModel):
    company_id: UUID
    screen_title: Optional[constr()]
    screen_sub_title: Optional[constr()]
    screen_order_number: conint()
    company_group_id: Optional[conint()]