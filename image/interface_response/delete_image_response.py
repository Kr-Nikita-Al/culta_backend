from uuid import UUID

from pydantic import BaseModel


class DeleteImageResponse(BaseModel):
    deleted_image_id: UUID
