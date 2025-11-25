from typing import Optional
from uuid import UUID
from fastapi import HTTPException

from pydantic import BaseModel, constr, conint, StrictBool, confloat, validator


class CreateImageRequest(BaseModel):
    image_id: UUID
    company_id: UUID
    title: constr()
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

    @validator("size")
    def validate_size(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect size")
        return value

    @validator("order_number")
    def validate_order_number(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect order_number")
        return value


