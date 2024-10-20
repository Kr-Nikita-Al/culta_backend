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
        company_row = res.fetchone()
        if company_row is not None:
            company_for_adding = company_row[0].company_id
        else:
            raise HTTPException(status_code=404,
                                detail='Company with id {0} was not exit'.format(company_id))

        new_company = ProductCardDB(
            company_id=company_for_adding,
            title=kwargs["title"],
            # sub_title=sub_title,
            # header=header,
            # description=description,
            # hint_header=hint_header,
            # hint_description=hint_description,
            # product_category=product_category,
            # custom_product_category=custom_product_category,
            # product_release_type=product_release_type,
            # allergens_list=allergens_list,
            # quantity_system=quantity_system,
            # tags=tags,
            # count_number=count_number,
            # price_field_1=price_field_1,
            # price_field_2=price_field_2,
            # cost_price_field_1=cost_price_field_1,
            # cost_price_field_2=cost_price_field_2,
            # cashback_field_1=cashback_field_1,
            # cashback_field_2=cashback_field_2,
            # product_quantity=product_quantity,
            # calorie_content=calorie_content,
            # proteins=proteins,
            # fats=fats, carbohydrates=carbohydrates,
            # cooking_time=cooking_time,
            # bonuses_payment=bonuses_payment,
            # single_product_type=single_product_type,
            # is_sharpness=is_sharpness,
            # is_hotness=is_hotness,
            # company_group_id=company_group_id,
            # product_image_id=product_image_id,
            # icon_image_id=icon_image_id
        )
        self.db_session.add(new_company)
        await self.db_session.flush()
        return new_company
