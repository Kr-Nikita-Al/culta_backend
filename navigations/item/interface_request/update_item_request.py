from datetime import time
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr, conint, StrictBool

from utils import LETTER_MATCH_PATTERN_PHONE


class UpdateItemRequest(BaseModel):
    item_type: Optional[constr()]
    item_column_order: Optional[conint()]
    item_row_order: Optional[conint()]

