from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from product_card.model_dal import ProductCardDal


async def __delete_product_card(product_card_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        deleted_product_card_id = await product_card_dal.delete_product_card(
            product_card_id=product_card_id
        )
        return deleted_product_card_id
