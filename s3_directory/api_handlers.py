from typing import Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from db.session import get_db
from s3_directory.storage.s3client import S3Client
from s3_directory.interface_request import CreateDirectoryRequest
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.constants import BASE_STORAGE_DIRECTORY

s3_directory_router = APIRouter()


@s3_directory_router.post("/create", response_model=Dict)
async def create_directory(body: CreateDirectoryRequest,
                           db: AsyncSession = Depends(get_db),
                           cur_user: UserDB = Depends(__get_user_from_token)) -> Dict:
    if body.dir_path.count('/') < 2 or body.dir_path[-1] != '/':
        raise HTTPException(status_code=422, detail='Incorrect directory path')
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
