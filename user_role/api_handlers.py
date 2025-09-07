from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

import company.actions
from db import UserDB
from db.session import get_db
from settings import ACCESS_SUPER_ADMINS
from user.actions import __get_user_from_token, __get_user_by_id
from user_role.actions import __grant_user_role, __get_user_roles, __revoke_user_role, \
    __get_user_roles_by_company_id, __get_user_role_model
from user_role.interface_request import GrantUserRoleRequest, RevokeUserRoleRequest
from user_role.interface_response import GrantUserRoleResponse, GetUserRolesResponse, RevokeUserRoleResponse
from utils.constants import PortalRole

user_role_router = APIRouter()


@user_role_router.get('/get_user_roles', response_model=List[GetUserRolesResponse])
async def get_user_roles_by_id(db: AsyncSession = Depends(get_db),
                               current_user: UserDB = Depends(__get_user_from_token)) -> List[GetUserRolesResponse]:
    user_roles = await __get_user_roles(current_user.user_id, db)
    if user_roles is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} have not any roles'.format(current_user.user_id))
    return user_roles


@user_role_router.get('/get_user_roles_in_company', response_model=List)
async def get_user_roles_in_company(company_id: UUID,
                                    db: AsyncSession = Depends(get_db),
                                    current_user: UserDB = Depends(__get_user_from_token)) -> List:
    return await __get_user_roles_by_company_id(current_user.user_id, company_id, db)


@user_role_router.post('/grant_super_admin_privilege', response_model=GrantUserRoleResponse)
async def grant_super_admin_privilege(db: AsyncSession = Depends(get_db),
                                      cur_user: UserDB = Depends(__get_user_from_token)) -> GrantUserRoleResponse:
    """
    Получить права супер администратора может только авторизованный клиент из списка ACCESS_SUPER_ADMINS
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права супер администратора
    """
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db)
    if cur_user_role_model.is_super_admin:
        raise HTTPException(status_code=409, detail='User is already super admin')
    if cur_user.email not in ACCESS_SUPER_ADMINS:
        raise HTTPException(status_code=403, detail='Forbidden')
    user_role_params = GrantUserRoleRequest(user_id=cur_user.user_id,
                                            role=PortalRole.PORTAL_ROLE_SUPER_ADMIN,
                                            creator_id=cur_user.user_id)
    try:
        return await __grant_user_role(user_role_params, db)
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')


@user_role_router.post('/grant_admin_privilege', response_model=GrantUserRoleResponse)
async def grant_admin_privilege(promo_user_id: UUID,
                                company_id: UUID,
                                db: AsyncSession = Depends(get_db),
                                cur_user: UserDB = Depends(__get_user_from_token)) -> GrantUserRoleResponse:
    """
    Получить права администратора может клиент от авторизованного пользователя с
    ролью администратора в этой компании или супер администратора
    :param promo_user_id: id пользователя, которому предоставляется роль
    :param company_id: id компании, в рамках которой предоставляется роль администратора
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    print(promo_user_id, company_id)
    # Проверка на возможность выделения прав авторизованным пользователем
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    if not cur_user_role_model.is_super_admin and not cur_user_role_model.is_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    if cur_user.user_id == promo_user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_obj = await company.actions.__get_company_by_id(company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail='Company with id {0} not found'.format(company_id))
    # Проверка на существование пользователя с ролью админа
    promo_user = await __get_user_by_id(user_id=promo_user_id, session=db)
    if promo_user is None:
        raise HTTPException(status_code=404, detail='User with id {0} not found'.format(promo_user_id))
    promo_user_role_model = await __get_user_role_model(user_id=promo_user_id, session=db,
                                                        company_id=company_id)
    if promo_user_role_model.is_admin:
        raise HTTPException(status_code=409,
                            detail='User with id {0} is already admin on this company'.format(promo_user_id))
    promo_user_role_params = GrantUserRoleRequest(user_id=promo_user_id, company_id=company_id,
                                                  role=PortalRole.PORTAL_ROLE_ADMIN,
                                                  creator_id=cur_user.user_id)
    try:
        return await __grant_user_role(promo_user_role_params, db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@user_role_router.delete('/revoke_admin_privilege', response_model=RevokeUserRoleResponse)
async def revoke_admin_privilege(demo_user_id: UUID,
                                 company_id: UUID,
                                 db: AsyncSession = Depends(get_db),
                                 cur_user: UserDB = Depends(__get_user_from_token)) -> RevokeUserRoleResponse:
    """
    Удалить права администратора может клиент от авторизованного пользователя с
    ролью супер администратора
    :param demo_user_id: id пользователя, которому предоставляется роль
    :param company_id: id компании, в рамках которой предоставляется роль администратора
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    # Проверка на возможность удаление авторизованным пользователем
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    if not cur_user_role_model.is_super_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    if cur_user.user_id == demo_user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_obj = await company.actions.__get_company_by_id(company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail='Company with id {0} not found'.format(company_id))
    # Проверка на существование пользователя с ролью админа
    demo_user = await __get_user_by_id(user_id=demo_user_id, session=db)
    if demo_user is None:
        raise HTTPException(status_code=404, detail='User with id {0} not found'.format(demo_user_id))
    demo_user_role_model = await __get_user_role_model(user_id=demo_user_id, session=db,
                                                       company_id=company_id)
    if not demo_user_role_model.is_admin:
        raise HTTPException(status_code=409, detail='User with id {0} has no admin privileges'.format(demo_user_id))
    demo_user_role_params = RevokeUserRoleRequest(user_id=demo_user_id,
                                                  company_id=company_id,
                                                  role=PortalRole.PORTAL_ROLE_ADMIN)
    try:
        revoked_user_id = await __revoke_user_role(demo_user_role_params, db)
        if revoked_user_id is None:
            raise HTTPException(status_code=404,
                                detail='User with id {0} with admin role in company with id {1} was deleted'.format(
                                    demo_user_id, company_id))
        return RevokeUserRoleResponse(revoked_user_id=revoked_user_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@user_role_router.post('/grant_moderator_privilege', response_model=GrantUserRoleResponse)
async def grant_moderator_privilege(promo_user_id: UUID,
                                    company_id: UUID,
                                    db: AsyncSession = Depends(get_db),
                                    cur_user: UserDB = Depends(__get_user_from_token)) -> GrantUserRoleResponse:
    """
    Получить права модератора может клиент от авторизованного пользователя с
    ролью администратора в этой компании
    :param promo_user_id: id пользователя, которому предоставляется роль
    :param company_id: id компании, в рамках которой предоставляется роль администратора
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    # Проверка на возможность выделения прав авторизованным пользователем
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    if not cur_user_role_model.is_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    if cur_user.user_id == promo_user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_obj = await company.actions.__get_company_by_id(company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail='Company with id {0} not found'.format(company_id))
    # Проверка на существование пользователя с ролью модератора
    promo_user = await __get_user_by_id(user_id=promo_user_id, session=db)
    if promo_user is None:
        raise HTTPException(status_code=404, detail='User with id {0} not found'.format(promo_user_id))
    promo_user_role_model = await __get_user_role_model(user_id=promo_user_id, session=db,
                                                        company_id=company_id)
    if promo_user_role_model.is_moderator:
        raise HTTPException(status_code=409,
                            detail='User with id {0} is already moderator on this company'.format(promo_user_id))
    promo_user_role_params = GrantUserRoleRequest(user_id=promo_user_id,
                                                  company_id=company_id,
                                                  role=PortalRole.PORTAL_ROLE_MODERATOR,
                                                  creator_id=cur_user.user_id)
    try:
        return await __grant_user_role(promo_user_role_params, db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@user_role_router.delete('/revoke_moderator_privilege', response_model=RevokeUserRoleResponse)
async def revoke_moderator_privilege(demo_user_id: UUID,
                                     company_id: UUID,
                                     db: AsyncSession = Depends(get_db),
                                     cur_user: UserDB = Depends(__get_user_from_token)) -> RevokeUserRoleResponse:
    """
    Удалить права администратора может клиент от авторизованного пользователя с
    ролью супер администратора
    :param demo_user_id: id пользователя, которому предоставляется роль
    :param company_id: id компании, в рамках которой предоставляется роль администратора
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    # Проверка на возможность удаление авторизованным пользователем
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    if not cur_user_role_model.is_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    if cur_user.user_id == demo_user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_obj = await company.actions.__get_company_by_id(company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail='Company with id {0} not found'.format(company_id))
    # Проверка на существование пользователя с ролью админа
    demo_user = await __get_user_by_id(user_id=demo_user_id, session=db)
    if demo_user is None:
        raise HTTPException(status_code=404, detail='User with id {0} not found'.format(demo_user_id))
    demo_user_role_model = await __get_user_role_model(user_id=demo_user_id, session=db,
                                                       company_id=company_id)
    if not demo_user_role_model.is_moderator:
        raise HTTPException(status_code=409, detail='User with id {0} has no moderator privileges'.format(demo_user_id))
    demo_user_role_params = RevokeUserRoleRequest(user_id=demo_user_id,
                                                  company_id=company_id,
                                                  role=PortalRole.PORTAL_ROLE_MODERATOR)
    try:
        revoked_user_id = await __revoke_user_role(demo_user_role_params, db)
        if revoked_user_id is None:
            raise HTTPException(status_code=404,
                                detail='User with id {0} with moderator role in company with id {1} was deleted'.format(
                                    demo_user_id, company_id))
        return RevokeUserRoleResponse(revoked_user_id=revoked_user_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')
