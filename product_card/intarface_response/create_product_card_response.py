from datetime import datetime
from uuid import UUID

from utils.base_model_response import BaseModelResponse


class CreateProductCardResponse(BaseModelResponse):
    company_id: UUID
    title: str

    # product_card_id: UUID
    # title: str
    # sub_title: str
    # header: str
    # description: str
    # hint_header: str
    # hint_description: str
    # product_category: str
    # custom_product_category: str
    # product_release_type: str
    # allergens_list: str
    # quantity_system: str
    # tags: str
    # bonuses_payment: bool
    # single_product_type: bool
    # is_sharpness: bool
    # is_hotness: bool
    # count_number: int
    # price_field_1: int
    # price_field_2: int
    # cost_price_field_1: int
    # cost_price_field_2: int
    # cashback_field_1: int
    # cashback_field_2: int
    # product_quantity: int
    # calorie_content: int
    # proteins: int
    # fats: int
    # carbohydrates: int
    # cooking_time: int
    # company_group_id: int
    # product_image_id: UUID
    # icon_image_id: UUID
    # creator_id: UUID
    # updater_id: UUID
    # time_created: datetime
    # time_updated: datetime