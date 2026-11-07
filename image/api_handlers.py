import os
import uuid
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

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

from company.modules import module_guard
image_router = APIRouter(dependencies=[Depends(module_guard('images'))])


@image_router.get('/pending_moves')
async def pending_moves(company_id: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                        db: AsyncSession = Depends(get_db), cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not (role.is_owner or role.is_admin or role.is_moderator):
        raise HTTPException(403, 'Forbidden')
    from image.move_diagnostics import list_pending
    return await list_pending(db, company_id, offset, limit)


@image_router.post('/cleanup_move')
async def cleanup_move(company_id: UUID, operation_id: UUID, db: AsyncSession = Depends(get_db),
                       cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not (role.is_owner or role.is_admin):
        raise HTTPException(403, 'Forbidden')
    from image.move_cleanup import cleanup_move as clean
    return await clean(db, company_id, operation_id, S3Client())


@image_router.get('/move_diagnostics')
async def move_diagnostics(company_id: UUID, operation_id: UUID, offset: int = Query(0, ge=0),
                           limit: int = Query(20, ge=1, le=50), db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not (role.is_owner or role.is_admin or role.is_moderator):
        raise HTTPException(403, 'Forbidden')
    from image.move_diagnostics import inspect_move
    return await inspect_move(db, company_id, operation_id, S3Client(), offset, limit)


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
        if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
            raise HTTPException(status_code=403, detail='Forbidden')
        # Count and byte quotas are checked under the company lock at creation.
        # Переименование названия изображения на служебное и сохранение в БД
        image_id = uuid.uuid4()
        new_filename = f"image_{image_id}" + os.path.splitext(file.filename)[1]
        image_body = CreateImageRequest(**data.dict(exclude_none=True), image_id=image_id, title=file.filename,
                                        file_name=new_filename, size=file.size)
        s3client = S3Client()

        async def upload_to_storage():
            await s3client.upload_file(file=file, file_path=data.file_path,
                                       filename=new_filename, company_id=data.company_id)

        image_obj = await __create_image(image_body=image_body, user_id=cur_user.user_id,
                                         session=db, before_commit=upload_to_storage)
        return image_obj
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="Bad request static_data")
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


@image_router.post("/create_loaded_url", response_model=CreateImageResponse)
async def create_loaded_url(body: CreateImageRequest,
                            db: AsyncSession = Depends(get_db),
                            cur_user: UserDB = Depends(__get_user_from_token)) -> CreateImageResponse:
    # Проверка прав на создание изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=body.company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        s3client = S3Client()
        url = await s3client.generate_put_presigned_url(file_path=body.file_path, file_name=body.file_name,
                                                        file_size=body.size, company_id=body.company_id)
        image = await __create_image(body, cur_user.user_id, db, pending_upload=True)
        return CreateImageResponse(
            url=url,
            image=image,
            required_headers={'If-None-Match': '*'}
        )
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


@image_router.get('/get_used_by_id', response_model=GetImageResponse)
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
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    images = await __get_images_by_company_id(company_id, db)
    return GetImagesInCompanyResponse(images=images)

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
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        s3client = S3Client()
        url = await s3client.generate_get_presigned_url(file_path=image_obj.file_path, file_name=image_obj.file_name,
                                                        company_id=image_obj.company_id)
        return GetImageResponse(url=url, image=image_obj)
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


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
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    images = await __get_images_by_company_id(company_id, db)
    return GetImagesInCompanyResponse(images=images)


@image_router.delete("/delete", response_model=DeleteImageResponse)
async def delete_image(image_id: UUID,
                       db: AsyncSession = Depends(get_db),
                       cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteImageResponse:
    del_image_obj = await __get_image_by_id(image_id=image_id, session=db, is_used=False)
    if del_image_obj is None:
        raise HTTPException(status_code=404, detail='Image with id {0} is not found'.format(image_id))
    # Проверка прав на создание карточки
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=del_image_obj.company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        s3client = S3Client()
        await s3client.delete_file(file_path=del_image_obj.file_path, file_name=del_image_obj.file_name,
                                   company_id=del_image_obj.company_id)
        del_image_id = await __delete_image(image_id, db)
        if del_image_id is None:
            raise HTTPException(status_code=404, detail='Image with id {0} was deleted before'.format(image_id))
        return DeleteImageResponse(deleted_image_id=del_image_id)
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


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
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные изображения
    upd_image_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if upd_image_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        upd_image_id = await __update_image_by_id(update_image_params=upd_image_params,
                                                  image_id=image_id, session=db)
        if upd_image_id is None:
            raise HTTPException(status_code=404, detail='Image with id {0} was deleted'.format(image_id))
        return UpdateImageResponse(updated_image_id=upd_image_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')


@image_router.get("/download")
async def download_image_proxy(image_id: UUID,
                               company_id: UUID,
                               filename: str = "image.png",
                               cur_user: UserDB = Depends(__get_user_from_token),
                               db: AsyncSession = Depends(get_db)):
    # Проверка прав на получение изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    image = await __get_image_by_id(image_id=image_id, session=db, is_used=False)
    if image is None or image.company_id != company_id:
        raise HTTPException(404, 'Image not found')
    data = await S3Client().download_image(image.file_path, image.file_name, company_id)
    name = image.file_name if filename == 'image.png' else filename
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    name = ''.join(c for c in name if ord(c) >= 32 and ord(c) != 127)[:200] or 'image.png'
    return Response(data, media_type='application/octet-stream', headers={
        'Content-Disposition': "attachment; filename=\"image\"; filename*=UTF-8''" + quote(name, safe=''),
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'private, no-store',
    })


@image_router.get("/get_folder_images")
async def get_folder_images(
        company_id: UUID,
        folder_path: str,
        cur_user: UserDB = Depends(__get_user_from_token),
        db: AsyncSession = Depends(get_db)
):
    """
    Возвращает все изображения в указанной папке (и подпапках, если нужно)
    с уже сгенерированными URL
    """
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    # Проверка прав на создание изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    images = await __get_images_by_company_id(company_id, db)
    # Фильтрация на нужную папку
    images = [image for image in images if folder_path == image.file_path]

    try:
        s3client = S3Client()
        # Генерация URL для каждого изображения
        for i in range(len(images)):
            try:
                url = await s3client.generate_get_presigned_url(file_path=images[i].file_path, file_name=images[i].file_name,
                                                                company_id=images[i].company_id)

                images[i].url = url
            except Exception:
                continue
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')
    print(images)
    return {"images": images}


@image_router.get("/refresh_folder_urls")
async def refresh_folder_urls(
        company_id: UUID,
        folder_path: str,
        cur_user: UserDB = Depends(__get_user_from_token),
        db: AsyncSession = Depends(get_db)
):
    """
    Обновляет URL для всех изображений в указанной папке
    """
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    # Проверка прав на создание изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    images = await __get_images_by_company_id(company_id, db)
    # Фильтрация на нужную папку
    # Match directory boundaries, not arbitrary substrings (tea != tea-old).
    folder_prefix = folder_path.rstrip('/') + '/'
    images = [image for image in images
              if (image.file_path.rstrip('/') + '/').startswith(folder_prefix)]

    try:
        s3client = S3Client()
        # Генерация URL для каждого изображения
        updated_urls = {}
        for image in images:
            updated_urls[image.image_id] = await s3client.generate_get_presigned_url(file_path=image.file_path,
                                                                                     file_name=image.file_name,
                                                                                     company_id=image.company_id)
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')
    return {"urls": updated_urls}
