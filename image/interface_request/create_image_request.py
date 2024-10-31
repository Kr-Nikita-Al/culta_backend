from typing import Optional

from pydantic import BaseModel, constr, conint, StrictBool


class CreateImageRequest(BaseModel):
    company_id: constr()
    title: Optional[constr()]
    type_col: Optional[constr()]
    image_type: Optional[constr()]
    url: Optional[constr()]
    resolution: Optional[constr()]
    tags: Optional[constr()]
    order_number: Optional[conint()]
    size: Optional[conint()]
    width: Optional[conint()]
    height: Optional[conint()]
    is_hidden: Optional[StrictBool]
    is_archived: Optional[StrictBool]
    company_group_id: Optional[constr()]

