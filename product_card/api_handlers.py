from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB
from image.actions import __update_status_used_image
from product_card.actions import __create_product_card, __get_product_card_by_id, __delete_product_card, \
    __update_product_card_by_id, __get_products_by_company_id
from product_card.interface_response import CreateProductCardResponse, DeleteProductCardResponse, \
    GetProductCardResponse, UpdateProductResponse, GetProductsInCompanyResponse
from product_card.interface_request import CreateProductCardRequest, UpdateProductCardRequest
from db.session import get_db
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.constants import EMPTY_UUID

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
        product_card_obj = await __create_product_card(body, cur_user.user_id, db)
        # Обновление статуса изображений в случае наличия их в body
        create_product_card_params = body.dict(exclude_none=True)
        images_upd_dict = {EMPTY_UUID: create_product_card_params[img_id] for img_id in
                           ['image_product_id', 'image_icon_id'] if img_id in create_product_card_params.keys()}
        if images_upd_dict != {}:
            await __update_status_used_image(images_upd_dict=images_upd_dict, session=db)
        return product_card_obj
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


@product_card_router.get('/get_product_cards_company_by_id', response_model=GetProductsInCompanyResponse)
async def get_product_cards_by_company_id(company_id: UUID,
                                          db: AsyncSession = Depends(get_db)) -> GetProductsInCompanyResponse:
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    products = await __get_products_by_company_id(company_id, db)
    return GetProductsInCompanyResponse(products=products)


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
        # Обновление статуса изображений в случае наличия их в upd_product_card_params
        images_upd_dict = {upd_product_card.__getattribute__(img_id): upd_product_card_params[img_id] for img_id in
                           ['image_product_id', 'image_icon_id'] if img_id in upd_product_card_params.keys()}
        if images_upd_dict != {}:
            await __update_status_used_image(images_upd_dict=images_upd_dict, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_product_card_id is None:
        raise HTTPException(status_code=404,
                            detail='Product card with id {0} was deleted'.format(product_card_id))
    return UpdateProductResponse(updated_product_card_id=updated_product_card_id)