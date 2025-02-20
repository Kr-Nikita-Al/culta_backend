from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB
from db.session import get_db
from image.actions import __create_image, __get_image_by_id, __delete_image, __update_image_by_id, \
    __get_images_by_company_id, __get_upd_file_data
from image.interface_request import CreateImageRequest, UpdateImageRequest, UploadImageRequest
from image.interface_response import CreateImageResponse, DeleteImageResponse, UpdateImageResponse, GetImageResponse, \
    GetImagesInCompanyResponse, CreateImageInterface
from s3_directory.storage import S3Client
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model

image_router = APIRouter()


@image_router.post("/upload", response_model=CreateImageInterface)
async def upload(metadata: str = Form(...),
                 file: UploadFile = File(...),
                 db: AsyncSession = Depends(get_db),
                 cur_user: UserDB = Depends(__get_user_from_token)) -> CreateImageInterface:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    try:
        data = UploadImageRequest.parse_raw(metadata)
        # Проверка прав на создание изображения
        cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=data.company_id)
        if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
            raise HTTPException(status_code=403, detail='Forbidden')
        s3client = S3Client()
        await s3client.upload_file(file=file, file_path=data.file_path, company_id=data.company_id)
        image_obj = await __create_image(image_body=CreateImageRequest(**data.dict(exclude_none=True),
                                                                       file_name=file.filename, size=file.size),
                                         user_id=cur_user.user_id, session=db)
        return image_obj
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="Bad request data")
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@image_router.post("/create_loaded_url", response_model=CreateImageResponse)
async def create_loaded_url(body: CreateImageRequest,
                            db: AsyncSession = Depends(get_db),
                            cur_user: UserDB = Depends(__get_user_from_token)) -> CreateImageResponse:
    # Проверка прав на создание изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        s3client = S3Client()
        url = await s3client.generate_put_presigned_url(file_path=body.file_path, file_name=body.file_name,
                                                        file_size=body.size, company_id=body.company_id)
        image = await __create_image(body, cur_user.user_id, db)
        return CreateImageResponse(
            url=url,
            image=image
        )
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@image_router.get('/get_used_by_id', response_model=GetImageResponse)
async def get_used_image_by_id(image_id: UUID,
                               db: AsyncSession = Depends(get_db)) -> GetImageResponse:
    image_obj = await __get_image_by_id(image_id=image_id, session=db, is_used=True)
    if image_obj is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} is not found or was not used before'.format(image_id))
    try:
        s3client = S3Client()
        url = await s3client.generate_get_presigned_url(file_path=image_obj.file_path, file_name=image_obj.file_name)
        return GetImageResponse(
            url=url,
            image=image_obj
        )
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@image_router.get('/get_by_id', response_model=GetImageResponse)
async def get_image_by_id(image_id: UUID,
                          db: AsyncSession = Depends(get_db),
                          cur_user: UserDB = Depends(__get_user_from_token)) -> GetImageResponse:
    image_obj = await __get_image_by_id(image_id=image_id, session=db, is_used=False)
    if image_obj is None:
        raise HTTPException(status_code=404,
                            detail='Image with id {0} is not found or was not used before'.format(image_id))
    # Проверка прав на выгрузку изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=image_obj.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        s3client = S3Client()
        url = await s3client.generate_get_presigned_url(file_path=image_obj.file_path, file_name=image_obj.file_name,
                                                        company_id=image_obj.company_id)
        return GetImageResponse(
            url=url,
            image=image_obj
        )
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@image_router.get('/get_images_company_by_id', response_model=GetImagesInCompanyResponse)
async def get_images_by_company_id(company_id: UUID,
                                   db: AsyncSession = Depends(get_db),
                                   cur_user: UserDB = Depends(__get_user_from_token)) -> GetImagesInCompanyResponse:
    # Проверка на существование компании
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    # Проверка прав на создание изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    images = await __get_images_by_company_id(company_id, db)
    return GetImagesInCompanyResponse(images=images)


@image_router.delete("/delete", response_model=DeleteImageResponse)
async def delete_image(image_id: UUID,
                       db: AsyncSession = Depends(get_db),
                       cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteImageResponse:
    del_image_obj = await __get_image_by_id(image_id=image_id, session=db, is_used=False)
    # Проверка прав на создание карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=del_image_obj.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    if del_image_obj is None:
        raise HTTPException(status_code=404, detail='Image with id {0} is not found'.format(image_id))
    # Попытка удалить изображение
    del_image_id = await __delete_image(image_id, db)
    if del_image_id is None:
        raise HTTPException(status_code=404, detail='Image with id {0} was deleted before'.format(image_id))
    try:
        s3client = S3Client()
        await s3client.delete_file(file_path=del_image_obj.file_path, file_name=del_image_obj.file_name,
                                   company_id=del_image_obj.company_id)
        return DeleteImageResponse(deleted_image_id=del_image_id)
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@image_router.patch('/update_by_id', response_model=UpdateImageResponse)
async def update_image_by_id(image_id: UUID,
                             body: UpdateImageRequest,
                             db: AsyncSession = Depends(get_db),
                             cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateImageResponse:
    # Проверка на существование обновляемой изображения
    upd_image = await __get_image_by_id(image_id=image_id, session=db, is_used=False)
    if upd_image is None:
        raise HTTPException(status_code=404, detail='Image with id {0} is not found'.format(image_id))
    # Проверка прав на получение изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=upd_image.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные изображения
    upd_image_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if upd_image_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        # Если изменили название или путь файла, то сторедже его также надо обновить
        dict_file_data = __get_upd_file_data(upd_image_params, upd_image)
        if dict_file_data != {}:
            s3client = S3Client()
            await s3client.update_file_place_object(old_file_name=upd_image.file_name,
                                                    old_file_path=upd_image.file_path,
                                                    new_file_path=dict_file_data['file_path'],
                                                    new_file_name=dict_file_data['file_name'],
                                                    company_id=upd_image.company_id)
        upd_image_id = await __update_image_by_id(update_image_params=upd_image_params,
                                                  image_id=image_id, session=db)
        if upd_image_id is None:
            raise HTTPException(status_code=404, detail='Image with id {0} was deleted'.format(image_id))
        return UpdateImageResponse(updated_image_id=upd_image_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
