from datetime import datetime
from uuid import UUID
from utils.base_model_response import BaseModelResponse


class CreateScreenResponse(BaseModelResponse):
    screen_id: UUID
    company_id: UUID
    company_group_id: int
    screen_title: str
    screen_sub_title: str
    screen_count_number: int
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime

