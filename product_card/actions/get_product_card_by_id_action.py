from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ProductCardDB
from product_card.interface_response import GetClientProductCardResponse, GetStaffProductCardResponse
from product_card.model_dal import ProductCardDal
from product_card.interface_response.get_product_card_response import GetManagementProductCardResponse


async def __get_product_card_by_id(product_card_id: UUID, is_staff: bool, session: AsyncSession, include_cost: bool = False) -> (
        Union)[GetStaffProductCardResponse, GetClientProductCardResponse, None]:
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        product_card = await product_card_dal.get_product_card_by_id(
            product_card_id=product_card_id
        )
    if product_card is None:
        return product_card
    product_card_dict = {c.name: getattr(product_card, c.name) for c in product_card.__table__.columns}
    product_card_dict['is_used'] = bool(product_card.is_used)
    if is_staff:
        if include_cost:
            return GetManagementProductCardResponse(**product_card_dict)
        return GetStaffProductCardResponse(**product_card_dict)
    return GetClientProductCardResponse(**product_card_dict)
