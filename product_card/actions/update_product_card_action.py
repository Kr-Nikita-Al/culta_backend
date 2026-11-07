from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from product_card.model_dal import ProductCardDal
from sqlalchemy import select
from product_card.versioning import check_product_version
from db import ProductCardDB
from utils.company_references import validate_company_references


async def __update_product_card_by_id(update_product_card_params: Dict, product_card_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    params = dict(update_product_card_params)
    expected = params.pop('version', None)
    async with session.begin():
        row = (await session.execute(select(ProductCardDB.company_id, ProductCardDB.version).where(
            ProductCardDB.product_card_id == product_card_id, ProductCardDB.is_active == True)
            .with_for_update())).one_or_none()
        if row is None:
            return None
        company_id, current_version = row
        check_product_version(expected, current_version)
        await validate_company_references(session, company_id, params,
            image_fields=('image_product_id', 'image_icon_id'))
        product_card = ProductCardDal(session)
        updated_product_card_id = await product_card.update_product_card(
            product_card_id=product_card_id,
            **params
        )
        return updated_product_card_id
