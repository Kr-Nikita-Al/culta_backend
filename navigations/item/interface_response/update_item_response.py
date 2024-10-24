from uuid import UUID

from pydantic import BaseModel


class UpdateItemResponse(BaseModel):
    updated_item_id: UUID
