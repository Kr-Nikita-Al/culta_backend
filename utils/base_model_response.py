from pydantic import BaseModel
from decimal import Decimal
from utils.money import encode_decimal


class BaseModelResponse(BaseModel):
    class Config:
        # Перевод в json пришедший dict
        orm_mode = True
        json_encoders = {Decimal: encode_decimal}
