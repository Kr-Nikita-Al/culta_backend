from utils.money import MoneyResponse
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import Optional

from db import STATUS_TYPE
from utils.base_model_response import BaseModelResponse


class CreateOrderResponse(BaseModelResponse):
    order_context: Optional[str] = None
    table_id: Optional[UUID] = None
    replayed: bool = False
    check_id: UUID = None
    order_id: UUID
    company_id: UUID
    price: MoneyResponse = Decimal('0.00')
    user_id: Optional[UUID] = None
    staff_id: UUID
    comment: str
    cocking_time: int
    status: STATUS_TYPE
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
