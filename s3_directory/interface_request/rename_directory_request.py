from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr, conint, StrictBool


class RenameDirectoryRequest(BaseModel):
    company_id: UUID
    old_dir_name: constr()
    new_dir_name: constr()
    dir_path: constr()


