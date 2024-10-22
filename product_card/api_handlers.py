from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from product_card.actions import __create_product_card, __get_product_card_by_id, __delete_product_card
from product_card.intarface_response import CreateProductCardResponse, DeleteProductCardResponse, GetProductCardResponse
from product_card.interface_request import CreateProductCardRequest
from db.session import get_db

product_card_router = APIRouter()


@product_card_router.post('/create', response_model=CreateProductCardResponse)
async def create_product_card(body: CreateProductCardRequest,
                              db: AsyncSession = Depends(get_db)) -> CreateProductCardResponse:
    return await __create_product_card(body, db)


@product_card_router.delete("/delete", response_model=DeleteProductCardResponse)
async def delete_product_card(product_card_id: UUID, db: AsyncSession = Depends(get_db)) -> DeleteProductCardResponse:
    product_card_for_deletion = await __get_product_card_by_id(product_card_id=product_card_id, session=db)
    if product_card_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found'.format(product_card_id))
    # Попытка удалить карточку продукта
    deleted_company_id = await __delete_product_card(product_card_id, db)
    if deleted_company_id is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} was deleted before'.format(product_card_id))
    return DeleteProductCardResponse(deleted_product_card_id=deleted_company_id)


@product_card_router.get('/get_by_id', response_model=GetProductCardResponse)
async def get_company_by_id(product_card_id: UUID, db: AsyncSession = Depends(get_db)) -> GetProductCardResponse:
    product_card = await __get_product_card_by_id(product_card_id, db)
    if product_card is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found or was deleted before'.format(product_card_id))
    return product_card
