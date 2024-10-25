from datetime import time
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr, conint, StrictBool

from utils import LETTER_MATCH_PATTERN_PHONE


class UpdateContainerRequest(BaseModel):
    container_title: Optional[constr()]
    container_sub_title: Optional[constr()]
    container_type: Optional[constr()]
    container_order: Optional[conint()]

