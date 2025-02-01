from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from product_card.actions import __create_product_card, __get_product_card_by_id, __delete_product_card, __update_product_card_by_id
from product_card.interface_response import CreateProductCardResponse, DeleteProductCardResponse, GetProductCardResponse, UpdateProductResponse
from product_card.interface_request import CreateProductCardRequest, UpdateProductCardRequest
from db.session import get_db
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model

product_card_router = APIRouter()


@product_card_router.post('/create', response_model=CreateProductCardResponse)
async def create_product_card(body: CreateProductCardRequest,
                              db: AsyncSession = Depends(get_db),
                              cur_user: UserDB = Depends(__get_user_from_token)) -> CreateProductCardResponse:
    # Проверка прав на создание карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        return await __create_product_card(body, cur_user.user_id, db)
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect data')


@product_card_router.delete("/delete", response_model=DeleteProductCardResponse)
async def delete_product_card(product_card_id: UUID,
                              db: AsyncSession = Depends(get_db),
                              cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteProductCardResponse:
    # Проверка на существование карточки
    del_product_card = await __get_product_card_by_id(product_card_id=product_card_id, session=db)
    if del_product_card is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found'.format(product_card_id))
    # Проверка прав на удаление карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=del_product_card.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка удалить карточку продукта
    del_product_card_id = await __delete_product_card(product_card_id, cur_user.user_id, db)
    if del_product_card_id is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} was deleted before'.format(product_card_id))
    return DeleteProductCardResponse(deleted_product_card_id=del_product_card_id)


@product_card_router.get('/get_by_id', response_model=GetProductCardResponse)
async def get_product_card_by_id(product_card_id: UUID, db: AsyncSession = Depends(get_db)) -> GetProductCardResponse:
    product_card_obj = await __get_product_card_by_id(product_card_id, db)
    if product_card_obj is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found or was deleted before'.format(product_card_id))
    return product_card_obj


@product_card_router.patch('/update_by_id', response_model=UpdateProductResponse)
async def update_product_card_by_id(product_card_id: UUID,
                                    body: UpdateProductCardRequest,
                                    db: AsyncSession = Depends(get_db),
                                    cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateProductResponse:
    # Проверка на существование обновляемой карточки продукта
    upd_product_card = await __get_product_card_by_id(product_card_id=product_card_id, session=db)
    if upd_product_card is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} is not found'.format(product_card_id))
    # Проверка прав на обновление карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=upd_product_card.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные карточки продукта
    upd_product_card_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if upd_product_card_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        upd_product_card_params['updater_id'] = cur_user.user_id
        updated_product_card_id = await __update_product_card_by_id(update_product_card_params=upd_product_card_params,
                                                                    product_card_id=product_card_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_product_card_id is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} was deleted'.format(product_card_id))
    return UpdateProductResponse(updated_product_card_id=updated_product_card_id)

