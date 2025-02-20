from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint, StrictBool


class DeleteDirectoryRequest(BaseModel):
    company_id: UUID
    dir_name: constr()
    dir_path: constr()
