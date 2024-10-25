from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from navigations.container.actions import __create_container, __get_container_by_id
from navigations.container.interface_request import CreateContainerRequest
from navigations.container.interface_response import CreateContainerResponse
from navigations.container.interface_response.get_container_response import GetContainerResponse

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
