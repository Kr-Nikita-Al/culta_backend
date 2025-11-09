import urllib
from typing import Dict
from urllib.parse import unquote
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from company.actions import __get_company_by_id
from db import UserDB
from db.session import get_db
from image.actions import __get_images_by_company_id, __update_image_by_id, __delete_image
from s3_directory.storage.s3client import S3Client
from s3_directory.interface_request import CreateDirectoryRequest, RenameDirectoryRequest, DeleteDirectoryRequest
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.constants import BASE_STORAGE_DIRECTORY

s3_directory_router = APIRouter()


@s3_directory_router.post("/create", response_model=Dict)
async def create_directory(body: CreateDirectoryRequest,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    if body.dir_path.count('/') < 2 or body.dir_path[-1] != '/' or body.dir_name[-1] != '/':
        raise HTTPException(status_code=422, detail='Incorrect directory path or name')
    # Проверка прав на создание директории внутри папки компании
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка совпадения пути папки компании, где хотят создать, с компанией, на которую выданы права доступа
    company_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(body.company_id))
    if company_dir_path != body.dir_path[:body.dir_path.index('/', body.dir_path.index('/') + 1)]:
        raise HTTPException(status_code=422, detail='Incorrect directory path')
    s3client = S3Client()
    await s3client.create_directory(dir_path=body.dir_path, dir_name=body.dir_name)
    return {'Success': 200}


@s3_directory_router.get("/get_objects_by_company_id", response_model=Dict)
async def get_objects_in_company(company_id: UUID,
                                 db: AsyncSession = Depends(get_db),
                                 cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    # Проверка прав на создание директории внутри папки компании
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    s3client = S3Client()
    obj_dict = await s3client.get_objects_by_dir_name(dir_name="company_{0}".format(str(company_id)))
    return obj_dict


@s3_directory_router.patch('/rename', response_model=Dict)
async def rename_directory(body: RenameDirectoryRequest,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    # Проверка на существование компании
    company = await __get_company_by_id(body.company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(body.company_id))
    # Проверка прав на получение изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        # Обновление директории в S3
        s3client = S3Client()
        await s3client.rename_directory(dir_path=body.dir_path, old_dir_name=body.old_dir_name,
                                        new_dir_name=body.new_dir_name, company_id=body.company_id)
        # Обновление директории в путях существующих изображений
        images = await __get_images_by_company_id(body.company_id, db)
        list_updated_id = []
        for image in images:
            if body.dir_path + body.old_dir_name in image.file_path:
                upd_image_id = await __update_image_by_id(update_image_params={'file_path': body.dir_path + body.new_dir_name},
                                                          image_id=image.image_id, session=db)
                list_updated_id.append(upd_image_id)
        return {'updated image id': list_updated_id}
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')


@s3_directory_router.delete("/delete", response_model=Dict)
async def delete_directory(body: DeleteDirectoryRequest,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    # Проверка прав на получение изображения
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=body.company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_moderator:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        s3client = S3Client()
        await s3client.delete_directory(dir_path=body.dir_path, dir_name=body.dir_name, company_id=body.company_id)
        images = await __get_images_by_company_id(body.company_id, db)
        # Удаление существующих изображений
        list_deleted_id = []
        for image in images:
            if body.dir_path + body.dir_name in image.file_path:
                del_image_id = await __delete_image(image.image_id, db)
                list_deleted_id.append(del_image_id)
        return {'deleted image id': list_deleted_id}
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


