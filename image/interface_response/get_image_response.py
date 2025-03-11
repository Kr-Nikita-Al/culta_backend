from typing import List
from uuid import UUID
from datetime import datetime
from pydantic import EmailStr

from utils.base_model_response import BaseModelResponse


class GetImageInterface(BaseModelResponse):
    image_id: UUID
    company_id: UUID
    file_name: str
    type_col: str
    image_type: str
    file_path: str
    resolution: str
    tags: str
    order_number: int
    size: int
    width: int
    height: int
    is_hidden: bool
    is_used: bool
    company_group_id: UUID
    creator_id: UUID
    time_created: datetime


class GetImageResponse(BaseModelResponse):
    url: str
    image: GetImageInterface
