from typing import Optional

from pydantic import BaseModel, constr, conint


class CreateContainerRequest(BaseModel):
    # screen_id: constr()
    container_title: Optional[constr()]
    container_sub_title: Optional[constr()]
    container_type: Optional[constr()]
    container_order: Optional[conint()]

