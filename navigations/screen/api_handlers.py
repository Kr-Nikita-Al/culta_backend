from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from navigations.screen.actions import __create_screen, __get_screen_by_id, __update_screen_by_id, __delete_screen
from navigations.screen.interface_request import CreateScreenRequest, UpdateScreenRequest
from navigations.screen.interface_response import CreateScreenResponse, GetScreenResponse, UpdateScreenResponse, DeleteScreenResponse

screen_router = APIRouter()


@screen_router.post('/create', response_model=CreateScreenResponse)
async def create_screen(body: CreateScreenRequest,
                        db: AsyncSession = Depends(get_db)) -> CreateScreenResponse:
    return await __create_screen(body, db)


@screen_router.get('/get_by_id', response_model=GetScreenResponse)
async def get_screen_by_id(screen_id: UUID, db: AsyncSession = Depends(get_db)) -> GetScreenResponse:
    screen = await __get_screen_by_id(screen_id=screen_id, session=db)
    if screen is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found or was deleted before'.format(screen_id))
    return screen


@screen_router.delete("/delete", response_model=DeleteScreenResponse)
async def delete_screen(screen_id: UUID, db: AsyncSession = Depends(get_db)) -> DeleteScreenResponse:
    screen_for_deletion = await __get_screen_by_id(screen_id=screen_id, session=db)
    if screen_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found'.format(screen_id))
    # Попытка удалить screen
    deleted_screen_id = await __delete_screen(screen_id, db)
    if deleted_screen_id is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} was deleted before'.format(deleted_screen_id))
    return DeleteScreenResponse(deleted_screen_id=deleted_screen_id)


@screen_router.patch('/update_by_id', response_model=UpdateScreenResponse)
async def update_screen_by_id(screen_id: UUID,
                              body: UpdateScreenRequest,
                              db: AsyncSession = Depends(get_db)) -> UpdateScreenResponse:
    # Проверка на существование обновляемый screen
    screen_for_update = await __get_screen_by_id(screen_id=screen_id, session=db)
    if screen_for_update is None:
        raise HTTPException(status_code=404,
                            detail='Screen with id {0} is not found'.format(screen_id))
    # Попытка обновить данные screen
    update_screen_params = body.dict(exclude_none=True)
    if update_screen_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_screen_id = await __update_screen_by_id(update_screen_params=update_screen_params,
                                                        screen_id=screen_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateScreenResponse(updated_screen_id=updated_screen_id)


