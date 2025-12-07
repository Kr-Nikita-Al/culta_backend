from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ProductCardDB
from product_card.interface_response import GetClientProductCardResponse, GetStaffProductCardResponse
from product_card.model_dal import ProductCardDal


async def __get_product_card_by_id(product_card_id: UUID, is_staff: bool, session: AsyncSession) -> (
        Union)[GetStaffProductCardResponse, GetClientProductCardResponse, None]:
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        product_card = await product_card_dal.get_product_card_by_id(
            product_card_id=product_card_id
        )
    if product_card is None:
        return product_card
    product_card_dict = {c.name: getattr(product_card, c.name) for c in product_card.__table__.columns}
    if is_staff:
        return GetStaffProductCardResponse(**product_card_dict)
    return GetClientProductCardResponse(**product_card_dict)