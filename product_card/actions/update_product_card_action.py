from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from product_card.model_dal import ProductCardDal


async def __update_product_card_by_id(update_product_card_params: Dict, product_card_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        product_card = ProductCardDal(session)
        updated_product_card_id = await product_card.update_product_card(
            product_card_id=product_card_id,
            **update_product_card_params
        )
        return updated_product_card_id
