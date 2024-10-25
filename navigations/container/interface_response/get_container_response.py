from typing import List
from uuid import UUID

from navigations.item.interface_response import GetItemResponse
from utils.base_model_response import BaseModelResponse


class GetContainerResponse(BaseModelResponse):
    container_id: UUID
    # screen_id: UUID
    container_title: str
    container_sub_title: str
    container_type: str
    container_order: int
    items: List[GetItemResponse]


