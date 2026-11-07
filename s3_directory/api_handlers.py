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
from s3_directory.interface_response import GetStorageLimitsInCompanyResponse
from s3_directory.storage.s3client import S3Client
from s3_directory.interface_request import CreateDirectoryRequest, RenameDirectoryRequest, DeleteDirectoryRequest
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.constants import BASE_STORAGE_DIRECTORY, QUOTA_COUNT_IMAGES_BY_COMPANY, QUOTA_STORAGE_SIZE, QUOTA_IMAGE_SIZE

s3_directory_router = APIRouter()


@s3_directory_router.get('/pending_deletions')
async def pending_deletions(company_id: UUID, db: AsyncSession = Depends(get_db),
                            cur_user: UserDB = Depends(__get_user_from_token)):
    from sqlalchemy import select
    from db import StorageDeleteDB
    role = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not (role.is_owner or role.is_admin or role.is_moderator):
        raise HTTPException(403, 'Forbidden')
    async with db.begin():
        rows = (await db.scalars(select(StorageDeleteDB).where(StorageDeleteDB.company_id == company_id,
            StorageDeleteDB.status == 'pending').order_by(StorageDeleteDB.created_at).limit(50))).all()
        return [{'operation_id': row.operation_id, 'prefix': row.prefix,
                 'file_count': len(row.keys), 'created_at': row.created_at} for row in rows]


@s3_directory_router.post('/retry_deletion')
async def retry_deletion(company_id: UUID, operation_id: UUID, db: AsyncSession = Depends(get_db),
                         cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not (role.is_owner or role.is_admin or role.is_moderator):
        raise HTTPException(403, 'Forbidden')
    from image.directory_delete import retry_directory_delete
    return await retry_directory_delete(db, company_id, operation_id, S3Client())


@s3_directory_router.post("/create", response_model=Dict)
async def create_directory(body: CreateDirectoryRequest,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    if body.dir_path.count('/') < 2 or body.dir_path[-1] != '/' or body.dir_name[-1] != '/':
        raise HTTPException(status_code=422, detail='Incorrect directory path or name')
    # Проверка прав на создание директории внутри папки компании
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=body.company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка совпадения пути папки компании, где хотят создать, с компанией, на которую выданы права доступа
    company_dir_path = BASE_STORAGE_DIRECTORY.COMPANY + "company_{0}".format(str(body.company_id))
    if company_dir_path != body.dir_path[:body.dir_path.index('/', body.dir_path.index('/') + 1)]:
        raise HTTPException(status_code=422, detail='Incorrect directory path')
    s3client = S3Client()
    from image.directory_delete import lock_company
    from image.delete_guard import require_no_pending_delete
    async with db.begin():
        await lock_company(db, body.company_id)
        await require_no_pending_delete(db, body.company_id)
        await s3client.create_directory(dir_path=body.dir_path, dir_name=body.dir_name)
    return {'Success': 200}


@s3_directory_router.get("/get_objects_by_company_id", response_model=Dict)
async def get_objects_in_company(company_id: UUID,
                                 db: AsyncSession = Depends(get_db),
                                 cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    # Проверка прав на создание директории внутри папки компании
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    s3client = S3Client()
    obj_dict = await s3client.get_objects_by_dir_name(dir_name=f'{BASE_STORAGE_DIRECTORY.COMPANY}company_{company_id}/')
    return obj_dict


@s3_directory_router.get('/get_storage_info_company_by_id', response_model=GetStorageLimitsInCompanyResponse)
async def get_storage_info_company_by_id(company_id: UUID,
                                         db: AsyncSession = Depends(get_db),
                                         cur_user: UserDB = Depends(__get_user_from_token)) -> GetStorageLimitsInCompanyResponse:
    """
    TODO: сделать гибкую настройку лимитов в зависимости от тарифа компании
    :param company_id:
    :param db:
    :param cur_user:
    :return:
    """
    # Проверка на существование компании
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    # Проверка прав на получение лимитов
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db, company_id=company_id)
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        images = await __get_images_by_company_id(company_id, db)
        s3client = S3Client()
        storage_objects = await s3client.get_objects_by_dir_name(dir_name=f'company_images/company_{company_id}/')
        return GetStorageLimitsInCompanyResponse(quota_count_images=QUOTA_COUNT_IMAGES_BY_COMPANY,
                                                 quota_storage_size=QUOTA_STORAGE_SIZE,
                                                 quota_image_size=QUOTA_IMAGE_SIZE,
                                                 used_count=len(images),
                                                 used_size=sum(list(storage_objects.values())))
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


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
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        from image.directory_move import rename_image_directory
        list_updated_id = await rename_image_directory(db, body, S3Client())
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
    if not (cur_user_role_model.is_owner or cur_user_role_model.is_admin or cur_user_role_model.is_moderator):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        from image.directory_delete import delete_image_directory
        list_deleted_id = await delete_image_directory(db, body, S3Client())
        return {'deleted image id': list_deleted_id}
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')
