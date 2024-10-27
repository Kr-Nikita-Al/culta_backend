from uuid import UUID

from pydantic import BaseModel


class UpdateScreenResponse(BaseModel):
    updated_screen_id: UUID
