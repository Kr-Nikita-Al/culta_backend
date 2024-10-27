from uuid import UUID

from pydantic import BaseModel


class DeleteScreenResponse(BaseModel):
    deleted_screen_id: UUID
