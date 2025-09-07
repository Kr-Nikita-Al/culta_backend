from pydantic import BaseModel
from uuid import UUID

from db import AuthProvider


class CreateAuthAccountRequest(BaseModel):
    provider: AuthProvider
    provider_user_id: str
    user_id: UUID
