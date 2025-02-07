from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from db.session import get_db
from image.actions import __create_image, __get_image_by_id, __delete_image, __update_image_by_id
from image.interface_request import CreateImageRequest, UpdateImageRequest
from image.interface_response import CreateImageResponse, GetImageInterface, DeleteImageResponse, UpdateImageResponse
from s3_directory.storage import S3Client
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.constants import BASE_STORAGE_DIRECTORY

image_router = APIRouter()


@image_router.post("/create", response_model=CreateImageResponse)
async def create(body: CreateImageRequest,
                 db: AsyncSession = Depends(get_db),
                 cur_user: UserDB = Depends(__get_user_from_token)) -> CreateImageResponse:
    # Проверка прав на создание карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        image = await __create_image(body, db)
        # Проверка совпадения пути папки компании, где хотят создать, с компанией, на которую выданы права доступа
        company_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(body.company_id))
        if company_dir_path != body.file_path[:body.file_path.index('/', body.file_path.index('/') + 1)]:
            raise HTTPException(status_code=422, detail='Incorrect directory path')
        s3client = S3Client()
        url = await s3client.generate_put_presigned_url(full_file_path=body.file_path + body.file_name, file_size=body.size)
        return CreateImageResponse(
            image_id=image.image_id,
            company_id=image.company_id,
            url=url
        )
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@image_router.delete("/delete", response_model=DeleteImageResponse)
async def delete_image(image_id: UUID,
                       db: AsyncSession = Depends(get_db)) -> DeleteImageResponse:
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


@image_router.get('/get_by_id', response_model=GetImageInterface)
async def get_image_by_id(image_id: UUID,
                          db: AsyncSession = Depends(get_db),
                          cur_user: UserDB = Depends(__get_user_from_token)) -> GetImageInterface:
    # Проверка прав на создание карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        image = await __get_image_by_id(image_id, db)
        if image is None:
            raise HTTPException(status_code=404,
                                detail='Image with id {0} is not found or was deleted before'.format(image_id))
        # Проверка совпадения пути папки компании, где хотят создать, с компанией, на которую выданы права доступа
        company_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(image.company_id))
        if company_dir_path != image.file_path[:image.file_path.index('/', image.file_path.index('/') + 1)]:
            raise HTTPException(status_code=422, detail='Incorrect directory path')
        s3client = S3Client()
        url = await s3client.generate_get_presigned_url(full_file_path=image.file_path + image.file_name)
        return CreateImageResponse(
            image_id=image.image_id,
            company_id=image.company_id,
            url=url
        )
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


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