from pydantic import BaseModel
from typing import List


class CityResponse(BaseModel):
    region: str
    city: str


class CitiesListResponse(BaseModel):
    cities: List[CityResponse]