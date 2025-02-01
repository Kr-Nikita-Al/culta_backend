from uuid import UUID

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from db.session import get_db
from navigations.actions import __check_permission_navigation
from navigations.screen.actions import __create_screen, __get_screen_by_id, __update_screen_by_id, __delete_screen, \
    __check_screen_order_numbers
from navigations.screen.interface_request import CreateScreenRequest, UpdateScreenRequest
from navigations.screen.interface_response import CreateScreenResponse, GetScreenResponse, UpdateScreenResponse, \
    DeleteScreenResponse
from user.actions import __get_user_from_token

screen_router = APIRouter()


@screen_router.post('/create', response_model=CreateScreenResponse)
async def create_screen(body: CreateScreenRequest,
                        db: AsyncSession = Depends(get_db),
                        cur_user: UserDB = Depends(__get_user_from_token)) -> CreateScreenResponse:
    # Проверка прав на создание скрина
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=body.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка существование скрина с таким же order_number в рамках одной компании и его корректность
    if not await __check_screen_order_numbers(session=db,
                                              order_number=body.screen_order_number,
                                              company_id=body.company_id):
        raise HTTPException(status_code=422,
                            detail='Screen with order number {0} already exist in this company or incorrect' \
                            .format(body.screen_order_number))
    try:
        return await __create_screen(body, cur_user.user_id, db)
    except (DBAPIError, IntegrityError, UniqueViolationError) as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@screen_router.get('/get_by_id', response_model=GetScreenResponse)
async def get_screen_by_id(screen_id: UUID, db: AsyncSession = Depends(get_db)) -> GetScreenResponse:
    screen = await __get_screen_by_id(screen_id=screen_id, session=db)
    if screen is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found or was deleted before'.format(screen_id))
    return screen


@screen_router.delete("/delete", response_model=DeleteScreenResponse)
async def delete_screen(screen_id: UUID,
                        db: AsyncSession = Depends(get_db),
                        cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteScreenResponse:
    del_screen_obj = await __get_screen_by_id(screen_id=screen_id, session=db)
    if del_screen_obj is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found'.format(screen_id))
    # Проверка прав на удаление скрина
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=del_screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка удалить screen
    deleted_screen_id = await __delete_screen(screen_id, db)
    if deleted_screen_id is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} was deleted before'.format(deleted_screen_id))
    return DeleteScreenResponse(deleted_screen_id=deleted_screen_id)


@screen_router.patch('/update_by_id', response_model=UpdateScreenResponse)
async def update_screen_by_id(screen_id: UUID,
                              body: UpdateScreenRequest,
                              db: AsyncSession = Depends(get_db),
                              cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateScreenResponse:
    # Проверка на существование обновляемый screen
    upd_screen_obj = await __get_screen_by_id(screen_id=screen_id, session=db)
    if upd_screen_obj is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found'.format(screen_id))
    # Проверка прав на обновление скрина
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=upd_screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные screen
    update_screen_params = body.dict(exclude_none=True)
    if update_screen_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        update_screen_params['updater_id'] = cur_user.user_id
        updated_screen_id = await __update_screen_by_id(update_screen_params=update_screen_params,
                                                        screen_id=screen_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateScreenResponse(updated_screen_id=updated_screen_id)
