from uuid import UUID

from utils.base_model_response import BaseModelResponse
from utils.constants import PortalRole


class GetUserRolesResponse(BaseModelResponse):
    company_id: UUID
    role: PortalRole
    avatar_id: UUID
