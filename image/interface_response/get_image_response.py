from typing import List
from uuid import UUID
from datetime import datetime
from pydantic import EmailStr

from utils.base_model_response import BaseModelResponse


class GetImageResponse(BaseModelResponse):
    image_id: UUID
    company_id: UUID
    title: str
    type_col: str
    image_type: str
    url: str
    resolution: str
    tags: str
    order_number: int
    size: int
    width: int
    height: int
    is_hidden: bool
    is_archived: bool
    company_group_id: UUID
    creator_id: UUID
    time_created: datetime
