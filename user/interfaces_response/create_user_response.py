import datetime
from uuid import UUID

from pydantic import EmailStr

from base_model_response import BaseModelResponse


class CreateUserResponse(BaseModelResponse):
    user_id: UUID
    user_name: str
    user_surname: str
    phone: str
    email: EmailStr
    is_active: bool
    creator_id: UUID
    updater_id: UUID
    time_created: datetime.datetime
    time_updated: datetime.datetime
