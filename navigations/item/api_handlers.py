from uuid import UUID

import psycopg2
import sqlalchemy
from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from db.session import get_db
from navigations.actions import __check_permission_navigation
from navigations.container.actions import __get_container_by_id
from navigations.item.actions import __create_item, __get_item_by_id, __delete_item, __update_item_by_id
from navigations.item.actions.check_item_positions import __check_item_positions
from navigations.item.interface_request import CreateItemRequest, UpdateItemRequest
from navigations.item.interface_response import CreateItemResponse, GetItemResponse, DeleteItemResponse, \
    UpdateItemResponse
from navigations.screen.actions import __get_screen_by_id
from product_card.actions import __get_product_card_by_id
from user.actions import __get_user_from_token

item_router = APIRouter()


@item_router.post('/create', response_model=CreateItemResponse)
async def create_item(body: CreateItemRequest,
                      db: AsyncSession = Depends(get_db),
                      cur_user: UserDB = Depends(__get_user_from_token)) -> CreateItemResponse:
    # Проверка на существование скрина и контейнера, в котором создается item
    container_obj = await __get_container_by_id(container_id=body.container_id, session=db)
    screen_obj = await __get_screen_by_id(screen_id=container_obj.screen_id, session=db)
    if container_obj is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found'.format(body.container_id))
    if screen_obj is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found'.format(container_obj.screen_id))
    # Проверка совпадение id компании продукта, который оборачивают item, с id компании скрина
    product_card_obj = await __get_product_card_by_id(product_card_id=body.product_card_id, session=db)
    if product_card_obj.company_id != screen_obj.company_id:
        raise HTTPException(status_code=404,
                            detail='Product card company with id {0} set in item of screen company with id {1}' \
                            .format(product_card_obj.company_id, screen_obj.company_id))
    # Проверка существование item с такой же позицией в рамках одного контейнера
    if not await __check_item_positions(session=db, row_order=body.item_row_order,
                                        column_order=body.item_column_order, container_id=body.container_id):
        raise HTTPException(status_code=422,
                            detail='Item with position ({0}, {1}) already exist in this container or incorrect' \
                            .format(body.item_row_order, body.item_column_order))
    # Проверка прав на создание item
    if not await __check_permission_navigation(user_id=cur_user.user_id, session=db,
                                               company_id=screen_obj.company_id):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        return await __create_item(body, db)
    except (DBAPIError, IntegrityError, UniqueViolationError) as e:
        raise HTTPException(status_code=422, detail='Incorrect data ')


@item_router.get('/get_by_id', response_model=GetItemResponse)
async def get_item_by_id(item_id: UUID, db: AsyncSession = Depends(get_db)) -> GetItemResponse:
    item = await __get_item_by_id(item_id=item_id, session=db)
    if item is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found or was deleted before'.format(item_id))
    return item


@item_router.delete("/delete", response_model=DeleteItemResponse)
async def delete_item(item_id: UUID,
                      db: AsyncSession = Depends(get_db),
                      cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteItemResponse:
    del_item_obj = await __get_item_by_id(item_id=item_id, session=db)
    if del_item_obj is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found'.format(item_id))
    # Проверка прав на удаление item
    container_obj = await __get_container_by_id(container_id=del_item_obj.container_id, session=db)
    screen_obj = await __get_screen_by_id(screen_id=container_obj.screen_id, session=db)
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка удалить item
    deleted_item_id = await __delete_item(item_id, db)
    if deleted_item_id is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} was deleted before'.format(deleted_item_id))
    return DeleteItemResponse(deleted_item_id=deleted_item_id)


@item_router.patch('/update_by_id', response_model=UpdateItemResponse)
async def update_item_by_id(item_id: UUID,
                            body: UpdateItemRequest,
                            db: AsyncSession = Depends(get_db),
                            cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateItemResponse:
    # Проверка на существование обновляемый item
    upd_item_obj = await __get_item_by_id(item_id=item_id, session=db)
    if upd_item_obj is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found'.format(item_id))
    # Проверка прав на создание item
    container_obj = await __get_container_by_id(container_id=upd_item_obj.container_id, session=db)
    screen_obj = await __get_screen_by_id(screen_id=container_obj.screen_id, session=db)
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные item
    upd_item_params = body.dict(exclude_none=True)
    if upd_item_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_item_id = await __update_item_by_id(update_item_params=upd_item_params,
                                                    item_id=item_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateItemResponse(updated_item_id=updated_item_id)
