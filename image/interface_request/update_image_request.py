from typing import Optional
from fastapi import HTTPException

from pydantic import BaseModel, constr, conint, StrictBool, validator


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

    @validator("width")
    def validate_width(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect width")
        return value

    @validator("height")
    def validate_height(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect height")
        return value


