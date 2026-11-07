from typing import Optional

from pydantic import BaseModel, constr, conint


class UpdateScreenRequest(BaseModel):
    class Config:
        extra = 'forbid'

    screen_title: Optional[constr()]
    screen_sub_title: Optional[constr()]
    screen_order_number: Optional[conint()]
    company_group_id: Optional[conint()]
