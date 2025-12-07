from datetime import datetime
from uuid import UUID

from utils.base_model_response import BaseModelResponse


class CreateProductCardResponse(BaseModelResponse):
    product_card_id: UUID
    company_id: UUID
    title: str
    title: str
    sub_title: str
    header: str
    description: str
    hint_header: str
    hint_description: str
    product_category: str
    custom_product_category: str
    product_release_type: str
    allergens_list: str
    quantity_system: str
    tags: str
    bonuses_payment: bool
    single_product_type: bool
    is_sharpness: bool
    is_hotness: bool
    is_active: bool
    count_number: int
    price: float
    cost_price: float
    cashback_perc: float
    product_quantity: int
    calorie_content: int
    proteins: int
    fats: int
    carbohydrates: int
    cooking_time: int
    company_group_id: int
    image_product_id: UUID
    image_icon_id: UUID
    creator_id: UUID
    updater_id: UUID
    time_created: datetime
    time_updated: datetime
