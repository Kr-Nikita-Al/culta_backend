from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint, StrictBool, confloat


class CreateImageRequest(BaseModel):
    company_id: UUID
    file_name: constr()
    file_path: constr()
    size: confloat()
    type_col: Optional[constr()]
    image_type: Optional[constr()]
    resolution: Optional[constr()]
    tags: Optional[constr()]
    order_number: Optional[conint()]
    width: Optional[conint()]
    height: Optional[conint()]
    is_hidden: Optional[StrictBool]
    is_archived: Optional[StrictBool]
    company_group_id: Optional[constr()]

