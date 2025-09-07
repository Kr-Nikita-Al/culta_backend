from uuid import UUID

from db import AuthProvider
from utils.base_model_response import BaseModelResponse


class CreateAuthAccountResponse(BaseModelResponse):
    auth_id: UUID
    provider: AuthProvider
    provider_user_id: str
    user_id: UUID
