from uuid import UUID

from pydantic import BaseModel

from utils.constants import PortalRole


class RevokeUserRoleRequest(BaseModel):
    user_id: UUID
    company_id: UUID
    role: PortalRole
