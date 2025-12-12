from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from product_card.interface_response import GetStaffProductsInCompanyResponse, GetClientProductsInCompanyResponse, \
    GetProductsInCompanyResponse, GetStaffProductCardResponse, GetClientProductCardResponse
from product_card.model_dal import ProductCardDal


async def __get_products_by_company_id(company_id: UUID, is_staff: bool, session: AsyncSession) -> (
        GetProductsInCompanyResponse):
    async with session.begin():
        product_card_dal = ProductCardDal(session)
        product_cards = await product_card_dal.get_products_by_company_id(
            company_id=company_id
        )

    if product_cards is None:
        return GetProductsInCompanyResponse(products=[])
    if is_staff:
        products = [GetStaffProductCardResponse.from_orm(card) for card in product_cards]
        return GetStaffProductsInCompanyResponse(products=products)
    products = [GetClientProductCardResponse.from_orm(card) for card in product_cards]
    return GetClientProductsInCompanyResponse(products=products)
