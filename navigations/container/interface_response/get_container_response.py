from pydantic import validator
from typing import List, Optional
from uuid import UUID

from navigations.item.interface_response import GetItemResponse
from utils.base_model_response import BaseModelResponse


class GetContainerResponse(BaseModelResponse):
    container_id: UUID
    screen_id: UUID
    container_title: str
    container_sub_title: str
    container_type: str
    container_order_number: int
    layout_x: Optional[int] = None
    layout_y: Optional[int] = None
    items: List[GetItemResponse]

    @validator('items', pre=True, allow_reuse=True)
    def published_children(cls, values):
        from navigations.publication import published
        return [value for value in values if published(value) and published(value.product_card_info)]
