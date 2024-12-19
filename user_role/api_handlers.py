from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB
from db.session import get_db
from settings import ACCESS_SUPER_ADMINS
from user.actions import __get_current_user_from_token, __get_user_by_id
from user_role.actions import __grant_user_role, __is_exist_user_role, __get_user_roles, __revoke_user_role, \
    __get_user_roles_by_company_id
from user_role.interface_request import GrantUserRoleRequest, RevokeUserRoleRequest
from user_role.interface_response import GrantUserRoleResponse, GetUserRolesResponse, RevokeUserRoleResponse
from utils.constants import PortalRole, EMPTY_UUID

user_role_router = APIRouter()


@user_role_router.post('/grant_super_admin_privilege', response_model=GrantUserRoleResponse)
async def grant_super_admin_privilege(db: AsyncSession = Depends(get_db),
                                      current_user: UserDB = Depends(
                                          __get_current_user_from_token)) -> GrantUserRoleResponse:
    """
    Получить права супер администратора может только авторизованный клиент из списка
    :param db: сессия
    :param current_user: авторизованный пользователь
    :return: id клиента, выданному права супер администратора
    """
    if current_user.email not in ACCESS_SUPER_ADMINS:
        raise HTTPException(status_code=403, detail='Forbidden')
    user_role_params = GrantUserRoleRequest(user_id=current_user.user_id,
                                            company_id=EMPTY_UUID,
                                            role=PortalRole.PORTAL_ROLE_SUPER_ADMIN
                                            )
    try:
        return await __grant_user_role(user_role_params, db)
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')


@user_role_router.post('/grant_admin_privilege', response_model=GrantUserRoleResponse)
async def grant_admin_privilege(user_id: UUID,
                                company_id_for_promotion: UUID,
                                db: AsyncSession = Depends(get_db),
                                current_user: UserDB = Depends(__get_current_user_from_token)) -> GrantUserRoleResponse:
    """
    Получить права администратора может клиент от авторизованного пользователя с
    ролью администратора в этой компании или супер администратора
    :param user_id: id пользователя, которому предоставляется роль
    :param company_id_for_promotion: id компании, в рамках которой предоставляется роль администратора
    :param db: сессия
    :param current_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    # Проверка на возможность удаление авторизованным пользователем
    is_exist_super_admin_role = await __is_exist_user_role(current_user.user_id, EMPTY_UUID,
                                                           PortalRole.PORTAL_ROLE_SUPER_ADMIN, db)
    is_exist_admin_role = await __is_exist_user_role(current_user.user_id, company_id_for_promotion,
                                                     PortalRole.PORTAL_ROLE_ADMIN, db)
    if is_exist_super_admin_role == False and is_exist_admin_role == False:
        raise HTTPException(status_code=403, detail='Forbidden')
    if current_user.user_id == user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_for_promotion = await __get_company_by_id(company_id_for_promotion, db)
    if company_for_promotion is None:
        raise HTTPException(status_code=404, detail='Company with id {0} not found'.format(company_id_for_promotion))
    # Проверка на существование пользователя с ролью админа
    user_for_promotion = await __get_user_by_id(user_id=user_id, session=db)
    if user_for_promotion is None:
        raise HTTPException(status_code=404, detail='User with id {0} not found'.format(user_id))
    is_exist_admin_role = await __is_exist_user_role(user_id,
                                                     company_id_for_promotion,
                                                     PortalRole.PORTAL_ROLE_ADMIN, db)
    if is_exist_admin_role:
        raise HTTPException(status_code=409,
                            detail='User with id {0} is already super_admin or admin on this company'.format(user_id))
    user_role_params = GrantUserRoleRequest(user_id=user_id,
                                            company_id=company_id_for_promotion,
                                            role=PortalRole.PORTAL_ROLE_ADMIN
                                            )
    try:
        return await __grant_user_role(user_role_params, db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@user_role_router.get('/get_user_roles', response_model=List[GetUserRolesResponse])
async def get_user_roles_by_id(db: AsyncSession = Depends(get_db),
                               current_user: UserDB = Depends(__get_current_user_from_token)) -> List[
    GetUserRolesResponse]:
    user_roles = await __get_user_roles(current_user.user_id, db)
    if user_roles is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} have not any roles'.format(current_user.user_id))
    return user_roles


@user_role_router.delete('/revoke_admin_privilege', response_model=RevokeUserRoleResponse)
async def revoke_admin_privilege(user_id: UUID,
                                 company_id_for_promotion: UUID,
                                 db: AsyncSession = Depends(get_db),
                                 current_user: UserDB = Depends(
                                     __get_current_user_from_token)) -> RevokeUserRoleResponse:
    # Проверка на возможность удаление авторизованным пользователем
    is_exist_super_admin_role = await __is_exist_user_role(current_user.user_id, EMPTY_UUID,
                                                           PortalRole.PORTAL_ROLE_SUPER_ADMIN, db)
    if not is_exist_super_admin_role:
        raise HTTPException(status_code=403, detail='Forbidden')
    if current_user.user_id == user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_for_promotion = await __get_company_by_id(company_id_for_promotion, db)
    if company_for_promotion is None:
        raise HTTPException(status_code=404, detail='Company with id {0} not found'.format(company_id_for_promotion))
    # Проверка на существование пользователя с ролью админа
    user_for_revoke = await __get_user_by_id(user_id=user_id, session=db)
    if user_for_revoke is None:
        raise HTTPException(status_code=404, detail='User with id {0} not found'.format(user_id))
    is_exist_admin_role = await __is_exist_user_role(user_id,
                                                     company_id_for_promotion,
                                                     PortalRole.PORTAL_ROLE_ADMIN, db)
    if not is_exist_admin_role:
        raise HTTPException(status_code=409, detail='User with id {0} has no admin privileges'.format(user_id))
    user_role_params = RevokeUserRoleRequest(user_id=user_id,
                                             company_id=company_id_for_promotion,
                                             role=PortalRole.PORTAL_ROLE_ADMIN
                                             )
    try:
        revoked_user_id = await __revoke_user_role(user_role_params, db)
        if revoked_user_id is None:
            raise HTTPException(status_code=404,
                                detail='User with id {0} with admin role in company with id {1} was deleted'.format(
                                    user_id, company_id_for_promotion))
        return RevokeUserRoleResponse(revoked_user_id=revoked_user_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@user_role_router.get('/get_user_roles_in_company', response_model=List)
async def get_user_roles_in_company(company_id: UUID,
                                    db: AsyncSession = Depends(get_db),
                                    current_user: UserDB = Depends(
                                            __get_current_user_from_token)) -> List:
    return await __get_user_roles_by_company_id(current_user.user_id, company_id, db)
