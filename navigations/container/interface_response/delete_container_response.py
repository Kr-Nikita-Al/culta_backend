from uuid import UUID

from pydantic import BaseModel


class DeleteContainerResponse(BaseModel):
    deleted_container_id: UUID
