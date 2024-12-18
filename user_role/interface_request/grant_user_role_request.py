from uuid import UUID

from pydantic import BaseModel

from utils.constants import PortalRole


class GrantUserRoleRequest(BaseModel):
    user_id: UUID
    company_id: UUID
    role: PortalRole
