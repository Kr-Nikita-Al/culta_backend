from typing import Optional
from fastapi import HTTPException

from pydantic import BaseModel, constr, confloat, conint, StrictBool, validator


class UpdateProductCardRequest(BaseModel):
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
    price: Optional[confloat()]
    cost_price: Optional[confloat()]
    cashback_perc: Optional[confloat()]
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
    image_product_id: Optional[constr()]
    image_icon_id: Optional[constr()]

    @validator("price")
    def validate_price(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect price")
        return value

    @validator("cost_price")
    def validate_cost_price(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect cost_price")
        return value

    @validator("cashback_perc")
    def validate_cashback_perc(cls, value):
        if value < 0:
            raise HTTPException(status_code=422, detail="Incorrect cashback_perc")
        return value

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
