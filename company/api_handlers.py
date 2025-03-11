from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __create_company, __delete_company, __get_all_companies, __get_company_by_id, \
    __update_company_by_id
from company.interface_request import CreateCompanyRequest, UpdateCompanyRequest
from company.interface_response import CreateCompanyResponse, DeleteCompanyResponse, GetAllCompanyResponse, \
    GetCompanyResponse, UpdateCompanyResponse
from db import UserDB
from db.session import get_db
from fastapi import APIRouter

from image.actions import __update_status_used_image
from s3_directory.storage import S3Client
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.constants import BASE_STORAGE_DIRECTORY

company_router = APIRouter()


@company_router.post("/create", response_model=CreateCompanyResponse)
async def create_company(body: CreateCompanyRequest,
                         db: AsyncSession = Depends(get_db),
                         cur_user: UserDB = Depends(__get_user_from_token)) -> CreateCompanyResponse:
    # Проверка прав на создание
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db)
    if not cur_user_role_model.is_super_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        company = await __create_company(body, cur_user.user_id, db)
        s3client = S3Client()
        await s3client.create_directory(dir_path=BASE_STORAGE_DIRECTORY.COMPANY,
                                        dir_name="company_{0}/".format(str(company.company_id)))
        return company
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect data')


@company_router.delete("/delete", response_model=DeleteCompanyResponse)
async def delete_company(company_id: UUID,
                         db: AsyncSession = Depends(get_db),
                         cur_user: UserDB = Depends(__get_user_from_token)) -> DeleteCompanyResponse:
    del_company = await __get_company_by_id(company_id=company_id, session=db)
    if del_company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found'.format(company_id))
    # Проверка прав на удаление
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db)
    if not cur_user_role_model.is_super_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка удалить компанию
    del_company_id = await __delete_company(company_id=company_id,
                                            updater_id=cur_user.user_id,
                                            session=db)
    if del_company_id is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} was deleted before'.format(company_id))
    return DeleteCompanyResponse(deleted_company_id=del_company_id)


@company_router.get('/get_by_id', response_model=GetCompanyResponse)
async def get_company_by_id(company_id: UUID, db: AsyncSession = Depends(get_db)) -> GetCompanyResponse:
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    return company


@company_router.get('/get_all', response_model=GetAllCompanyResponse)
async def get_all_companies(db: AsyncSession = Depends(get_db)) -> GetAllCompanyResponse:
    companies = await __get_all_companies(db)
    if companies is None:
        raise HTTPException(status_code=404,
                            detail='Table Company is empty')
    return GetAllCompanyResponse(companies=companies)


@company_router.patch('/update_by_id', response_model=UpdateCompanyResponse)
async def update_company_by_id(company_id: UUID,
                               body: UpdateCompanyRequest,
                               db: AsyncSession = Depends(get_db),
                               cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateCompanyResponse:
    # Проверка прав на обновление данных
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    if not cur_user_role_model.is_admin and not cur_user_role_model.is_super_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка на существование обновляемой компании
    upd_company = await __get_company_by_id(company_id=company_id, session=db)
    if upd_company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found'.format(company_id))
    # Попытка обновить данные компании
    upd_company_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if upd_company_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        upd_company_params['updater_id'] = cur_user.user_id
        updated_company_id = await __update_company_by_id(update_company_params=upd_company_params,
                                                          company_id=company_id, session=db)
        # Обновление статуса изображений в случае наличия их в upd_company_params
        images_upd_dict = {upd_company.__getattribute__(img_id): upd_company_params[img_id] for img_id in
                           ['image_picture_id', 'image_icon_id'] if img_id in upd_company_params.keys()}
        if images_upd_dict != {}:
            await __update_status_used_image(images_upd_dict=images_upd_dict, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_company_id is None:
        raise HTTPException(status_code=404,  detail='Company with id {0} was deleted'.format(company_id))
    return UpdateCompanyResponse(updated_company_id=updated_company_id)
