from typing import Optional

from pydantic import BaseModel, constr, conint, StrictBool


class CreateProductCardRequest(BaseModel):
    company_id: str
    title: Optional[constr(min_length=1, max_length=20)]
    # sub_title: constr(min_length=1, max_length=50)
    # header: constr()
    # description: constr()
    # hint_header: constr()
    # hint_description: constr()
    # product_category: constr()
    # custom_product_category: constr()
    # product_release_type: constr()
    # allergens_list: constr()
    # quantity_system: constr()
    # tags: constr()
    # count_number: conint()
    # price_field_1: conint()
    # price_field_2: conint()
    # cost_price_field_1: conint()
    # cost_price_field_2: conint()
    # cashback_field_1: conint()
    # cashback_field_2: conint()
    # product_quantity: conint()
    # calorie_content: conint()
    # proteins: conint()
    # fats: conint()
    # carbohydrates: conint()
    # cooking_time: conint()
    # bonuses_payment: StrictBool
    # single_product_type: StrictBool
    # is_sharpness: StrictBool
    # is_hotness: StrictBool
    # company_group_id: conint()
    # product_image_id: constr()
    # icon_image_id: constr()
