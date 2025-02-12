from datetime import datetime
from uuid import UUID

from utils.base_model_response import BaseModelResponse


class CreateImageInterface(BaseModelResponse):
    image_id: UUID
    company_id: UUID
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


class CreateImageResponse(BaseModelResponse):
    url: str
    image: CreateImageInterface
