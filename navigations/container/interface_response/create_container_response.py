from uuid import UUID
from utils.base_model_response import BaseModelResponse


class CreateContainerResponse(BaseModelResponse):
    container_id: UUID
    screen_id: UUID
    container_title: str
    container_sub_title: str
    container_type: str
    container_order: int

