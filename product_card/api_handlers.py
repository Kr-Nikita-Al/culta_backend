from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from product_card.actions import __create_product_card, __get_product_card_by_id, __delete_product_card, __update_product_card_by_id
from product_card.interface_response import CreateProductCardResponse, DeleteProductCardResponse, GetProductCardResponse, UpdateProductResponse
from product_card.interface_request import CreateProductCardRequest, UpdateProductCardRequest
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
    deleted_product_card_id = await __delete_product_card(product_card_id, db)
    if deleted_product_card_id is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} was deleted before'.format(product_card_id))
    return DeleteProductCardResponse(deleted_product_card_id=deleted_product_card_id)


@product_card_router.get('/get_by_id', response_model=GetProductCardResponse)
async def get_product_card_by_id(product_card_id: UUID, db: AsyncSession = Depends(get_db)) -> GetProductCardResponse:
    product_card = await __get_product_card_by_id(product_card_id, db)
    if product_card is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found or was deleted before'.format(product_card_id))
    return product_card


@product_card_router.patch('/update_by_id', response_model=UpdateProductResponse)
async def update_product_card_by_id(product_card_id: UUID,
                                    body: UpdateProductCardRequest,
                                    db: AsyncSession = Depends(get_db)) -> UpdateProductResponse:
    # Проверка на существование обновляемой карточки продукта
    product_card_for_update = await __get_product_card_by_id(product_card_id=product_card_id, session=db)
    if product_card_for_update is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found'.format(product_card_id))
    # Попытка обновить данные карточки продукта
    update_product_card_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if update_product_card_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_product_card_id = await __update_product_card_by_id(update_product_card_params=update_product_card_params,
                                                                    product_card_id=product_card_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_product_card_id is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} was deleted'.format(product_card_id))
    return UpdateProductResponse(updated_product_card_id=updated_product_card_id)

