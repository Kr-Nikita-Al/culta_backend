from typing import Union, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from product_card.model_dal import ProductCardDal


async def __get_products_by_company_id(company_id: UUID, session: AsyncSession) -> List:
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        product_cards = await product_card_dal.get_products_by_company_id(
            company_id=company_id
        )
        return product_cards
