from uuid import UUID

from pydantic import BaseModel


class RevokeUserRoleResponse(BaseModel):
    revoked_user_id: UUID

