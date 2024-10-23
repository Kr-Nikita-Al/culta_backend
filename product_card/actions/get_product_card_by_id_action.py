from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import CompanyDB
from product_card.model_dal import ProductCardDal


async def __get_product_card_by_id(product_card_id: UUID, session: AsyncSession) -> Union[CompanyDB, None]:
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        product_card = await product_card_dal.get_product_card_by_id(
            product_card_id=product_card_id
        )
        return product_card
