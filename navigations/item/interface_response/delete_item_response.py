from uuid import UUID

from pydantic import BaseModel


class DeleteItemResponse(BaseModel):
    deleted_item_id: UUID
