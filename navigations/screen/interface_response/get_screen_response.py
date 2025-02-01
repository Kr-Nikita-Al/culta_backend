from datetime import datetime
from typing import List
from uuid import UUID

from navigations.container.interface_response import GetContainerResponse
from utils.base_model_response import BaseModelResponse


class GetScreenResponse(BaseModelResponse):
    screen_id: UUID
    company_id: UUID
    company_group_id: int
    screen_title: str
    screen_sub_title: str
    screen_order_number: int
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
    containers: List[GetContainerResponse]


