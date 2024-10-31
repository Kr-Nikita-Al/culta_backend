from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from image.actions import __create_image, __get_image_by_id, __delete_image, __update_image_by_id
from image.interface_request import CreateImageRequest, UpdateImageRequest
from image.interface_response import CreateImageResponse, GetImageResponse, DeleteImageResponse, UpdateImageResponse

image_router = APIRouter()


@image_router.post("/create", response_model=CreateImageResponse)
async def create_image(body: CreateImageRequest, db: AsyncSession = Depends(get_db)) -> CreateImageResponse:
    return await __create_image(body, db)


@image_router.delete("/delete", response_model=DeleteImageResponse)
async def delete_image(image_id: UUID, db: AsyncSession = Depends(get_db)) -> DeleteImageResponse:
    image_for_deletion = await __get_image_by_id(image_id=image_id, session=db)
    if image_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} is not found'.format(image_id))
    # Попытка удалить изображение
    deleted_image_id = await __delete_image(image_id, db)
    if deleted_image_id is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} was deleted before'.format(image_id))
    return DeleteImageResponse(deleted_image_id=deleted_image_id)


@image_router.get('/get_by_id', response_model=GetImageResponse)
async def get_image_by_id(image_id: UUID, db: AsyncSession = Depends(get_db)) -> GetImageResponse:
    image = await __get_image_by_id(image_id, db)
    if image is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} is not found or was deleted before'.format(image_id))
    return image


@image_router.patch('/update_by_id', response_model=UpdateImageResponse)
async def update_image_by_id(image_id: UUID,
                             body: UpdateImageRequest,
                             db: AsyncSession = Depends(get_db)) -> UpdateImageResponse:
    # Проверка на существование обновляемой изображения
    image_for_update = await __get_image_by_id(image_id=image_id, session=db)
    if image_for_update is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} is not found'.format(image_id))
    # Попытка обновить данные изображения
    update_image_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if update_image_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_image_id = await __update_image_by_id(update_image_params=update_image_params,
                                                      image_id=image_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_image_id is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} was deleted'.format(image_id))
    return UpdateImageResponse(updated_image_id=updated_image_id)