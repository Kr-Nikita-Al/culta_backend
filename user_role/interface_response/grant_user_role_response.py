from uuid import UUID

from pydantic import BaseModel


class GrantUserRoleResponse(BaseModel):
    granted_user_id: UUID

