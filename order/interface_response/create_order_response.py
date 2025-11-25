from datetime import datetime
from uuid import UUID

from db import STATUS_TYPE
from utils.base_model_response import BaseModelResponse


class CreateOrderResponse(BaseModelResponse):
    order_id: UUID
    company_id: UUID
    user_id: UUID
    staff_id: UUID
    comment: str
    cocking_time: int
    status: STATUS_TYPE
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
