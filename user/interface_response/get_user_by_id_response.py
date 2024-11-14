from datetime import datetime
from uuid import UUID

from pydantic import EmailStr

from utils.base_model_response import BaseModelResponse


class GetUserResponse(BaseModelResponse):
    user_id: UUID
    name: str
    surname: str
    phone: str
    email: EmailStr
    is_active: bool
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
