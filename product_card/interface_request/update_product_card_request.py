from datetime import time
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, validator, constr, EmailStr, conint, StrictBool

from utils import LETTER_MATCH_PATTERN_PHONE


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
    price_field_1: Optional[conint()]
    price_field_2: Optional[conint()]
    cost_price_field_1: Optional[conint()]
    cost_price_field_2: Optional[conint()]
    cashback_field_1: Optional[conint()]
    cashback_field_2: Optional[conint()]
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
    product_image_id: Optional[conint()]
    icon_image_id: Optional[conint()]
