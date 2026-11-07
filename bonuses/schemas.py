from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from utils.base_model_response import BaseModelResponse
from utils.money import MoneyResponse


class BonusEntryResponse(BaseModelResponse):
    transaction_id: UUID
    company_id: Optional[UUID]
    check_id: Optional[UUID]
    kind: str
    amount: Decimal
    balance_before: MoneyResponse
    balance_after: MoneyResponse
    created_at: datetime
