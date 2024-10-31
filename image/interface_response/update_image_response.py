from uuid import UUID

from pydantic import BaseModel


class UpdateImageResponse(BaseModel):
    updated_image_id: UUID
