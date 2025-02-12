from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint, StrictBool, confloat


class CreateImageRequest(BaseModel):
    company_id: UUID
    file_name: constr()
    file_path: constr()
    size: confloat()
    width: conint()
    height: conint()
    type_col: Optional[constr()]
    image_type: Optional[constr()]
    resolution: Optional[constr()]
    tags: Optional[constr()]
    order_number: Optional[conint()]
    is_hidden: Optional[StrictBool]
    company_group_id: Optional[constr()]

