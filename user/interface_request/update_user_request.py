from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr

from utils.regex import LETTER_MATCH_PATTERN_PHONE, LETTER_MATCH_PATTERN_NAME


class UpdateUserRequest(BaseModel):
    name: Optional[constr(min_length=1)]
    surname: Optional[constr(min_length=1)]
    phone: Optional[constr(min_length=1)]
    email: Optional[EmailStr]
    password: Optional[constr(min_length=1)]

    @validator("phone")
    def validate_phone(cls, value):
        if not LETTER_MATCH_PATTERN_PHONE.match(value):
            raise HTTPException(
                status_code=422, detail="Incorrect phone"
            )
        return value

    @validator("name")
    def validate_name(cls, value):
        if not LETTER_MATCH_PATTERN_NAME.match(value):
            raise HTTPException(
                status_code=422, detail="Name should contains only letters"
            )
        return value

    @validator("surname")
    def validate_surname(cls, value):
        if not LETTER_MATCH_PATTERN_NAME.match(value):
            raise HTTPException(
                status_code=422, detail="Surname should contains only letters"
            )
        return value
