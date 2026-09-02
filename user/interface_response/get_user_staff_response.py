from typing import List
from uuid import UUID

from utils.base_model_response import BaseModelResponse
from utils.constants import PortalRole


class UserWithRolesResponse(BaseModelResponse):
    user_id: UUID
    name: str
    surname: str
    roles: List[PortalRole]

    class Config:
        from_attributes = True
