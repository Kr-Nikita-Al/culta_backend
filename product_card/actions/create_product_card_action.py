from sqlalchemy.ext.asyncio import AsyncSession

from product_card.intarface_response import CreateProductCardResponse
from product_card.interface_request import CreateProductCardRequest
from product_card.model_dal import ProductCardDal


async def __create_product_card(product_card_body: CreateProductCardRequest, session: AsyncSession) -> CreateProductCardResponse:
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        product_card_db = await product_card_dal.create_product_card(
            product_card_body.__dict__
        )
        return CreateProductCardResponse(
            company_id=product_card_db.company_id,
            title=product_card_db.title,
            product_card_id=product_card_db.product_card_id,
            sub_title=product_card_db.sub_title,
            header=product_card_db.header,
            description=product_card_db.description,
            hint_header=product_card_db.hint_header,
            hint_description=product_card_db.hint_description,
            product_category=product_card_db.product_category,
            custom_product_category=product_card_db.custom_product_category,
            product_release_type=product_card_db.product_release_type,
            quantity_system=product_card_db.quantity_system,
            tags=product_card_db.tags,
            count_number=product_card_db.count_number,
            price_field_1=product_card_db.price_field_1,
            price_field_2=product_card_db.price_field_2,
            cost_price_field_1=product_card_db.cost_price_field_1,
            cost_price_field_2=product_card_db.cost_price_field_2,
            cashback_field_1=product_card_db.cashback_field_1,
            cashback_field_2=product_card_db.cashback_field_2,
            product_quantity=product_card_db.product_quantity,
            calorie_content=product_card_db.calorie_content,
            proteins=product_card_db.proteins,
            fats=product_card_db.fats,
            carbohydrates=product_card_db.carbohydrates,
            cooking_time=product_card_db.cooking_time,
            bonuses_payment=product_card_db.bonuses_payment,
            single_product_type=product_card_db.single_product_type,
            is_sharpness=product_card_db.is_sharpness,
            is_hotness=product_card_db.is_hotness,
            company_group_id=product_card_db.company_group_id,
            product_image_id=product_card_db.product_image_id,
            icon_image_id=product_card_db.icon_image_id,
            creator_id=product_card_db.creator_id,
            updater_id=product_card_db.updater_id,
            time_created=product_card_db.time_created,
            time_updated=product_card_db.time_updated,
            allergens_list=product_card_db.allergens_list
        )