from uuid import UUID

from pydantic import BaseModel


class DeleteUserResponse(BaseModel):
    deleted_user_id: UUID