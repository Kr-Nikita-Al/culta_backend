from uuid import UUID

from pydantic import BaseModel


class UpdateContainerResponse(BaseModel):
    updated_container_id: UUID
