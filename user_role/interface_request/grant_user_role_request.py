from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from utils.constants import PortalRole


class GrantUserRoleRequest(BaseModel):
    user_id: UUID
    role: PortalRole
    company_id: Optional[UUID]
    creator_id: Optional[UUID]
