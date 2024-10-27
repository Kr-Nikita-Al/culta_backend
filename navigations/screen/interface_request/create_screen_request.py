from typing import Optional

from pydantic import BaseModel, constr, conint


class CreateScreenRequest(BaseModel):
    company_id: constr()
    screen_title: Optional[constr()]
    screen_sub_title: Optional[constr()]
    screen_count_number: Optional[conint()]
    company_group_id: Optional[conint()]