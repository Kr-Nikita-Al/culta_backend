from fastapi import HTTPException

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from db import CompanyDB, ProductCardDB


class ProductCardDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_product_card(self, kwargs) -> ProductCardDB:

        company_id = kwargs["company_id"]
        query = select(CompanyDB).where(CompanyDB.company_id == company_id,
                                        CompanyDB.is_active == True)
        res = await self.db_session.execute(query)
        product_card_row = res.fetchone()
        if product_card_row is not None:
            company_for_adding = product_card_row[0].company_id
        else:
            raise HTTPException(status_code=404,
                                detail='Company with id {0} was not exit'.format(company_id))

        new_product_card = ProductCardDB(
            company_id=company_for_adding,
            title=kwargs["title"],
            sub_title=kwargs["sub_title"],
            header=kwargs["header"],
            description=kwargs["description"],
            hint_header=kwargs["hint_header"],
            hint_description=kwargs["hint_description"],
            product_category=kwargs["product_category"],
            custom_product_category=kwargs["custom_product_category"],
            product_release_type=kwargs["product_release_type"],
            allergens_list=kwargs["allergens_list"],
            quantity_system=kwargs["quantity_system"],
            tags=kwargs["tags"],
            count_number=kwargs["count_number"],
            price_field_1=kwargs["price_field_1"],
            price_field_2=kwargs["price_field_2"],
            cost_price_field_1=kwargs["cost_price_field_1"],
            cost_price_field_2=kwargs["cost_price_field_2"],
            cashback_field_1=kwargs["cashback_field_1"],
            cashback_field_2=kwargs["cashback_field_2"],
            product_quantity=kwargs["product_quantity"],
            calorie_content=kwargs["calorie_content"],
            proteins=kwargs["proteins"],
            fats=kwargs["fats"],
            carbohydrates=kwargs["carbohydrates"],
            cooking_time=kwargs["cooking_time"],
            bonuses_payment=kwargs["bonuses_payment"],
            single_product_type=kwargs["single_product_type"],
            is_sharpness=kwargs["is_sharpness"],
            is_hotness=kwargs["is_hotness"],
            company_group_id=kwargs["company_group_id"],
            product_image_id=kwargs["product_image_id"],
            icon_image_id=kwargs["icon_image_id"]
        )
        self.db_session.add(new_product_card)
        await self.db_session.flush()
        return new_product_card