from uuid import UUID

from asyncpg import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from db.session import get_db
from navigations.actions import __check_permission_navigation
from navigations.container.actions import __create_container, __get_container_by_id, __delete_container, \
    __update_container_by_id, __check_container_order_numbers
from navigations.container.interface_request import CreateContainerRequest, UpdateContainerRequest
from navigations.container.interface_response import CreateContainerResponse, GetContainerResponse, \
    DeleteContainerResponse, UpdateContainerResponse
from navigations.screen.actions import __get_screen_by_id
from user.actions import __get_user_from_token

container_router = APIRouter()


@container_router.post('/create', response_model=CreateContainerResponse)
async def create_container(body: CreateContainerRequest,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> CreateContainerResponse:
    # Проверка на существование screen, в котором создается контейнера
    screen_obj = await __get_screen_by_id(screen_id=body.screen_id, session=db)
    if screen_obj is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found'.format(body.screen_id))
    # Проверка существование контейнера с таким же order_number в рамках одного скрина и его корректность
    if not await __check_container_order_numbers(session=db,
                                                 order_number=body.container_order_number,
                                                 screen_id=body.screen_id):
        raise HTTPException(status_code=422,
                            detail='Container with order number {0} already exist in this screen or incorrect' \
                            .format(body.container_order_number))
    # Проверка прав на создание контейнера
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        return await __create_container(body, db)
    except (DBAPIError, IntegrityError, UniqueViolationError) as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@container_router.get('/get_by_id', response_model=GetContainerResponse)
async def get_container_by_id(container_id: UUID, db: AsyncSession = Depends(get_db)) -> GetContainerResponse:
    container = await __get_container_by_id(container_id=container_id, session=db)
    if container is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found or was deleted before'.format(container_id))
    return container


@container_router.delete("/delete", response_model=DeleteContainerResponse)
async def delete_container(container_id: UUID,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteContainerResponse:
    # Проверка на существование удаляемого контейнера
    del_container_obj = await __get_container_by_id(container_id=container_id, session=db)
    if del_container_obj is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found'.format(container_id))
    # Проверка прав на удаление контейнера
    screen_obj = await __get_screen_by_id(screen_id=del_container_obj.screen_id, session=db)
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка удалить контейнер
    deleted_container_id = await __delete_container(container_id, db)
    if deleted_container_id is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} was deleted before'.format(deleted_container_id))
    return DeleteContainerResponse(deleted_container_id=deleted_container_id)


@container_router.patch('/update_by_id', response_model=UpdateContainerResponse)
async def update_container_by_id(container_id: UUID,
                                 body: UpdateContainerRequest,
                                 db: AsyncSession = Depends(get_db),
                                 cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateContainerResponse:
    # Проверка на существование обновляемого контейнера
    upd_container_obj = await __get_container_by_id(container_id=container_id, session=db)
    if upd_container_obj is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found'.format(container_id))
    # Проверка прав на удаление контейнера
    screen_obj = await __get_screen_by_id(screen_id=upd_container_obj.screen_id, session=db)
    if not await __check_permission_navigation(user_id=cur_user.user_id,
                                               company_id=screen_obj.company_id,
                                               session=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные container
    update_container_params = body.dict(exclude_none=True)
    if update_container_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_container_id = await __update_container_by_id(update_container_params=update_container_params,
                                                              container_id=container_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateContainerResponse(updated_container_id=updated_container_id)
