from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint


class CreateContainerRequest(BaseModel):
    screen_id: UUID
    container_title: Optional[constr()]
    container_sub_title: Optional[constr()]
    container_type: Optional[constr()]
    container_order_number: conint()

