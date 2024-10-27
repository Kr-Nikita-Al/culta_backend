from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from navigations.container.actions import __create_container, __get_container_by_id, __delete_container, __update_container_by_id
from navigations.container.interface_request import CreateContainerRequest, UpdateContainerRequest
from navigations.container.interface_response import CreateContainerResponse, GetContainerResponse, DeleteContainerResponse, UpdateContainerResponse

container_router = APIRouter()


@container_router.post('/create', response_model=CreateContainerResponse)
async def create_container(body: CreateContainerRequest,
                           db: AsyncSession = Depends(get_db)) -> CreateContainerResponse:
    return await __create_container(body, db)


@container_router.get('/get_by_id', response_model=GetContainerResponse)
async def get_container_by_id(container_id: UUID, db: AsyncSession = Depends(get_db)) -> GetContainerResponse:
    container = await __get_container_by_id(container_id=container_id, session=db)
    if container is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found or was deleted before'.format(container_id))
    return container


@container_router.delete("/delete", response_model=DeleteContainerResponse)
async def delete_container(container_id: UUID, db: AsyncSession = Depends(get_db)) -> DeleteContainerResponse:
    container_for_deletion = await __get_container_by_id(container_id=container_id, session=db)
    if container_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found'.format(container_id))
    # Попытка удалить container
    deleted_container_id = await __delete_container(container_id, db)
    if deleted_container_id is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} was deleted before'.format(deleted_container_id))
    return DeleteContainerResponse(deleted_container_id=deleted_container_id)


@container_router.patch('/update_by_id', response_model=UpdateContainerResponse)
async def update_container_by_id(container_id: UUID,
                            body: UpdateContainerRequest,
                            db: AsyncSession = Depends(get_db)) -> UpdateContainerResponse:
    # Проверка на существование обновляемый container
    container_for_update = await __get_container_by_id(container_id=container_id, session=db)
    if container_for_update is None:
        raise HTTPException(status_code=404,
                            detail='Container with id {0} is not found'.format(container_id))
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


