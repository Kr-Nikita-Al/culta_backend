from utils.money import Money, Percentage
from typing import Optional
from uuid import UUID
from fastapi import HTTPException

from pydantic import BaseModel, constr, conint, StrictBool, validator


class UpdateProductCardRequest(BaseModel):
    class Config:
        extra = 'forbid'

    version: Optional[conint(strict=True, ge=1)] = None

    title: Optional[constr(min_length=1, max_length=20)]
    sub_title: Optional[constr(min_length=1, max_length=50)]
    header: Optional[constr()]
    description: Optional[constr()]
    hint_header: Optional[constr()]
    hint_description: Optional[constr()]
    product_category: Optional[constr()]
    custom_product_category: Optional[constr()]
    product_release_type: Optional[constr()]
    allergens_list: Optional[constr()]
    quantity_system: Optional[constr()]
    tags: Optional[constr()]
    count_number: Optional[conint()]
    price: Optional[Money]
    cost_price: Optional[Money]
    cashback_perc: Optional[Percentage]
    product_quantity: Optional[conint()]
    calorie_content: Optional[conint()]
    proteins: Optional[conint()]
    fats: Optional[conint()]
    carbohydrates: Optional[conint()]
    cooking_time: Optional[conint()]
    bonuses_payment: Optional[StrictBool]
    single_product_type: Optional[StrictBool]
    is_sharpness: Optional[StrictBool]
    is_hotness: Optional[StrictBool]
    is_active: Optional[StrictBool]
    company_group_id: Optional[conint()]
    image_product_id: Optional[UUID]
    image_icon_id: Optional[UUID]




    @validator("product_quantity")
    def validate_product_quantity(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect product_quantity")
        return value

    @validator("calorie_content")
    def validate_calorie_content(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect calorie_content")
        return value

    @validator("proteins")
    def validate_proteins(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect proteins")
        return value

    @validator("fats")
    def validate_fats(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect fats")
        return value

    @validator("carbohydrates")
    def validate_carbohydrates(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect carbohydrates")
        return value

    @validator("cooking_time")
    def validate_cooking_time(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect cooking_time")
        return value
