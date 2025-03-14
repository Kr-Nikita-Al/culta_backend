from typing import Optional

from pydantic import BaseModel, constr, conint, StrictBool


class UpdateImageRequest(BaseModel):
    title: Optional[constr()]
    file_name: Optional[constr()]
    type_col: Optional[constr()]
    image_type: Optional[constr()]
    file_path: Optional[constr()]
    resolution: Optional[constr()]
    tags: Optional[constr()]
    order_number: Optional[conint()]
    width: Optional[conint()]
    height: Optional[conint()]
    is_hidden: Optional[StrictBool]
    company_group_id: Optional[constr()]

