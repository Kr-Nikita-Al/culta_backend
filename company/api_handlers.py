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

from user.actions import __get_current_user_from_token
from user_role.actions import __is_exist_user_role
from utils.constants import EMPTY_UUID, PortalRole

company_router = APIRouter()


@company_router.post("/create", response_model=CreateCompanyResponse)
async def create_company(body: CreateCompanyRequest,
                         db: AsyncSession = Depends(get_db),
                         current_user: UserDB = Depends(__get_current_user_from_token)) -> CreateCompanyResponse:
    # Проверка прав на создание
    is_exist_super_admin_role = await __is_exist_user_role(current_user.user_id, EMPTY_UUID,
                                                           PortalRole.PORTAL_ROLE_SUPER_ADMIN, db)
    if not is_exist_super_admin_role:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        return await __create_company(body, current_user.user_id, db)
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect data')


@company_router.delete("/delete", response_model=DeleteCompanyResponse)
async def delete_company(company_id: UUID,
                         db: AsyncSession = Depends(get_db),
                         current_user: UserDB = Depends(__get_current_user_from_token)) -> DeleteCompanyResponse:
    company_for_deletion = await __get_company_by_id(company_id=company_id, session=db)
    if company_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found'.format(company_id))
    # Проверка прав на удаление
    is_exist_super_admin_role = await __is_exist_user_role(current_user.user_id, EMPTY_UUID,
                                                           PortalRole.PORTAL_ROLE_SUPER_ADMIN, db)
    if not is_exist_super_admin_role:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка удалить компанию
    deleted_company_id = await __delete_company(company_id, db)
    if deleted_company_id is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} was deleted before'.format(company_id))
    return DeleteCompanyResponse(deleted_company_id=deleted_company_id)


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
                               current_user: UserDB = Depends(__get_current_user_from_token)) -> UpdateCompanyResponse:
    # Проверка прав на обновление данных
    is_exist_admin_role = await __is_exist_user_role(current_user.user_id, company_id,
                                                     PortalRole.PORTAL_ROLE_ADMIN, db)
    if not is_exist_admin_role:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка на существование обновляемой компании
    company_for_update = await __get_company_by_id(company_id=company_id, session=db)
    if company_for_update is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} is not found'.format(company_id))
    # Попытка обновить данные компании
    update_company_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if update_company_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        update_company_params['updater_id'] = current_user.user_id
        updated_company_id = await __update_company_by_id(update_company_params=update_company_params,
                                                          company_id=company_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    if updated_company_id is None:
        raise HTTPException(status_code=404,
                            detail='Company with id {0} was deleted'.format(company_id))
    return UpdateCompanyResponse(updated_company_id=updated_company_id)
