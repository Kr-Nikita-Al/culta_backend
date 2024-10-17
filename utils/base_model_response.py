from pydantic import BaseModel


class BaseModelResponse(BaseModel):
    class Config:
        # Перевод в json пришедший dict
        orm_mode = True
