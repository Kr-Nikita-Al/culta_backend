from uuid import UUID

from pydantic import BaseModel


class UpdateUserResponse(BaseModel):
    updated_user_id: UUID
