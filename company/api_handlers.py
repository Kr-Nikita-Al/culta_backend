from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __create_company, __delete_company, __get_all_companies, __get_company_by_id, \
    __update_company_by_id, __get_company_products_by_id
from company.interface_request import CreateCompanyRequest, UpdateCompanyRequest
from company.interface_response import CreateCompanyResponse, DeleteCompanyResponse, GetAllCompanyResponse, \
    GetCompanyResponse, UpdateCompanyResponse,  GetAllCompanyProductsResponse
from db import UserDB
from db.session import get_db
from sqlalchemy.exc import DBAPIError
from fastapi import APIRouter

from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model

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
        return await __create_company(body, cur_user.user_id, db)
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


@company_router.get('/get_products_by_id', response_model=GetAllCompanyProductsResponse)
async def get_company_products_by_id(company_id: UUID, db: AsyncSession = Depends(get_db)) -> GetAllCompanyProductsResponse:
    company = await __get_company_by_id(company_id, db)
    if company is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found or was deleted before'.format(company_id))
    products = await __get_company_products_by_id(company_id, db)
    return GetAllCompanyProductsResponse(products=products)


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
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_company_id is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} was deleted'.format(company_id))
    return UpdateCompanyResponse(updated_company_id=updated_company_id)
