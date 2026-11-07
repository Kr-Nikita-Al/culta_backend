from datetime import datetime
from typing import Optional
from uuid import UUID
from db import STATUS_TYPE
from utils.base_model_response import BaseModelResponse


class StatusHistoryResponse(BaseModelResponse):
    event_id: UUID
    order_id: UUID
    old_status: Optional[STATUS_TYPE]
    new_status: STATUS_TYPE
    actor_id: UUID
    changed_at: datetime
    reason: Optional[str]
