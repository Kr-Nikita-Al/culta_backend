from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

import company.actions
from db import UserDB, UserRoleDB, CompanyDB
from db.session import get_db
from settings import ACCESS_SUPER_ADMINS
from user.actions import __get_user_from_token, __get_user_by_id
from user_role.actions import __grant_user_role, __get_user_roles, __revoke_user_role, \
    __get_user_roles_by_company_id, __get_user_role_model, __check_permissions_granting_or_revoking_user_roles
from user_role.interface_request import GrantUserRoleRequest, RevokeUserRoleRequest
from user_role.interface_response import GrantUserRoleResponse, GetUserRolesResponse, RevokeUserRoleResponse
from user_role.model_user_roles import UserRoleModel
from utils.constants import PortalRole, CHANGEABLE_PORTAL_ROLES, EMPTY_UUID

user_role_router = APIRouter()


class StaffCandidate(BaseModel):
    user_id: UUID
    name: str
    surname: str
    email_hint: str


class StaffSearchResponse(BaseModel):
    users: List[StaffCandidate]
    has_more: bool


@user_role_router.get('/staff_table')
async def staff_table(company_id: UUID, page: int = Query(0, ge=0),
                      db: AsyncSession = Depends(get_db), cur_user: UserDB = Depends(__get_user_from_token)):
    roles = (await db.execute(select(UserRoleDB.role).where(
        UserRoleDB.user_id == cur_user.user_id, UserRoleDB.is_active.is_(True),
        or_(UserRoleDB.company_id == company_id,
            (UserRoleDB.company_id == EMPTY_UUID) & (UserRoleDB.role == PortalRole.PORTAL_ROLE_SUPER_ADMIN))))).scalars().all()
    model = UserRoleModel(user_roles=roles)
    if not (model.is_super_admin or model.is_owner or model.is_admin):
        raise HTTPException(403, 'Forbidden')
    if not await db.scalar(select(CompanyDB.company_id).where(
            CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True))):
        raise HTTPException(404, 'Company not found')
    has_staff_role = select(UserRoleDB.relation_id).where(
        UserRoleDB.user_id == UserDB.user_id, UserRoleDB.company_id == company_id,
        UserRoleDB.is_active.is_(True), UserRoleDB.role.in_(CHANGEABLE_PORTAL_ROLES)).exists()
    users = (await db.execute(select(UserDB.user_id, UserDB.name, UserDB.surname, UserDB.account_status).where(
        has_staff_role).order_by(UserDB.surname, UserDB.name, UserDB.user_id).offset(page*50).limit(51))).all()
    rows = (await db.execute(select(UserRoleDB.user_id, UserRoleDB.role).where(
        UserRoleDB.company_id == company_id, UserRoleDB.user_id.in_([u.user_id for u in users[:50]]),
        UserRoleDB.is_active.is_(True), UserRoleDB.role.in_(CHANGEABLE_PORTAL_ROLES)))).all()
    grants = [r for r in CHANGEABLE_PORTAL_ROLES if await __check_permissions_granting_or_revoking_user_roles(model,r,True)]
    revokes = [r for r in CHANGEABLE_PORTAL_ROLES if await __check_permissions_granting_or_revoking_user_roles(model,r,False)]
    return {'users':[{'user_id':u.user_id,'name':u.name,'surname':u.surname,
        'roles':list({r.role for r in rows if r.user_id==u.user_id}),
        'self':u.user_id==cur_user.user_id, 'can_grant':u.account_status=='confirmed'} for u in users[:50]],
        'grantable_roles':grants,'revocable_roles':revokes,'has_more':len(users)>50}


@user_role_router.get('/search_staff_candidates', response_model=StaffSearchResponse)
async def search_staff_candidates(company_id: UUID, role: PortalRole,
                                 action: Literal['grant', 'revoke'],
                                 q: str = Query(..., min_length=2, max_length=100),
                                 db: AsyncSession = Depends(get_db),
                                 cur_user: UserDB = Depends(__get_user_from_token)):
    terms = q.split()
    if len(' '.join(terms)) < 2 or role not in CHANGEABLE_PORTAL_ROLES:
        raise HTTPException(422, 'Invalid search')
    # Read active roles directly: disabled privileges must not permit user discovery.
    roles = (await db.execute(select(UserRoleDB.role).where(
        UserRoleDB.user_id == cur_user.user_id, UserRoleDB.is_active.is_(True),
        or_(UserRoleDB.company_id == company_id,
            (UserRoleDB.company_id == EMPTY_UUID) &
            (UserRoleDB.role == PortalRole.PORTAL_ROLE_SUPER_ADMIN))))).scalars().all()
    if not await __check_permissions_granting_or_revoking_user_roles(
            UserRoleModel(user_roles=roles), role, action == 'grant'):
        raise HTTPException(403, 'Forbidden')
    if not await db.scalar(select(CompanyDB.company_id).where(
            CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True))):
        raise HTTPException(404, 'Company not found')
    stmt = select(UserDB.user_id, UserDB.name, UserDB.surname, UserDB.email).where(
        UserDB.user_id != cur_user.user_id, UserDB.is_active.is_(True))
    if action == 'grant':
        stmt = stmt.where(UserDB.account_status == 'confirmed')
    else:
        stmt = stmt.where(select(UserRoleDB.relation_id).where(
            UserRoleDB.user_id == UserDB.user_id, UserRoleDB.company_id == company_id,
            UserRoleDB.role == role, UserRoleDB.is_active.is_(True)).exists())
    for term in terms:
        stmt = stmt.where(or_(func.lower(UserDB.name).contains(term.lower(), autoescape=True),
                              func.lower(UserDB.surname).contains(term.lower(), autoescape=True)))
    rows = (await db.execute(stmt.order_by(UserDB.surname, UserDB.name, UserDB.user_id).limit(21))).all()
    return StaffSearchResponse(users=[StaffCandidate(
        user_id=row.user_id, name=row.name, surname=row.surname,
        email_hint=row.email[:1] + '***@' + row.email.rsplit('@', 1)[-1]) for row in rows[:20]],
        has_more=len(rows) > 20)


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

# @user_role_router.post('/set_avatar_by_role', response_model=List)
# async def set_avatar_by_role(company_id: UUID,
#                              db: AsyncSession = Depends(get_db),
#                              current_user: UserDB = Depends(__get_user_from_token)) -> List:
#     return await __get_user_roles_by_company_id(current_user.user_id, company_id, db)


@user_role_router.post('/grant_super_admin_privilege', response_model=GrantUserRoleResponse)
async def grant_super_admin_privilege(db: AsyncSession = Depends(get_db),
                                      cur_user: UserDB = Depends(__get_user_from_token)) -> GrantUserRoleResponse:
    """
    Получить права супер администратора может только авторизованный клиент из списка ACCESS_SUPER_ADMINS
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права супер администратора
    """
    from user.account_status import require_confirmed
    require_confirmed(cur_user)
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
        raise HTTPException(status_code=422, detail='Incorrect static_data')
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')


@user_role_router.post('/grant_staff_privilege', response_model=GrantUserRoleResponse)
async def grant_staff_privilege(promo_user_id: UUID,
                                company_id: UUID,
                                role: PortalRole,
                                db: AsyncSession = Depends(get_db),
                                cur_user: UserDB = Depends(__get_user_from_token)) -> GrantUserRoleResponse:
    """
    Метод получения прав в рамках компании
    :param promo_user_id: id пользователя, которому предоставляется роль
    :param company_id: id компании, в рамках которой предоставляется роль
    :param role: выдаваемая роль в компании
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    # Проверка на корректность заданной роли
    if role not in CHANGEABLE_PORTAL_ROLES:
        raise HTTPException(status_code=422, detail='Incorrect static_data')
    # Проверка на возможность выделения прав авторизованным пользователем
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    is_permitted = await __check_permissions_granting_or_revoking_user_roles(cur_user_role_model, role)
    if not is_permitted:
        raise HTTPException(status_code=403, detail='Forbidden')
    if cur_user.user_id == promo_user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_obj = await company.actions.__get_company_by_id(company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail=f'Company with id {company_id} not found')
    # Проверка на существование пользователя с ролью
    promo_user = await __get_user_by_id(user_id=promo_user_id, session=db)
    if promo_user is None:
        raise HTTPException(status_code=404, detail=f'User with id {promo_user_id} not found')
    from user.account_status import require_confirmed
    require_confirmed(promo_user)
    promo_user_role_model = await __get_user_role_model(user_id=promo_user_id, session=db,
                                                        company_id=company_id)
    if promo_user_role_model.check_existing_role(role):
        raise HTTPException(status_code=409,
                            detail=f'User with id {promo_user_id} is already {role} on this company')
    promo_user_role_params = GrantUserRoleRequest(user_id=promo_user_id,
                                                  company_id=company_id,
                                                  role=role,
                                                  creator_id=cur_user.user_id)
    try:
        return await __grant_user_role(promo_user_role_params, db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


@user_role_router.delete('/revoke_staff_privilege', response_model=RevokeUserRoleResponse)
async def revoke_staff_privilege(demo_user_id: UUID,
                                 company_id: UUID,
                                 role: PortalRole,
                                 db: AsyncSession = Depends(get_db),
                                 cur_user: UserDB = Depends(__get_user_from_token)) -> RevokeUserRoleResponse:
    """
    Метод отзыва прав в рамках компании
    :param demo_user_id: id пользователя, которому предоставляется роль
    :param company_id: id компании, в рамках которой предоставляется роль
    :param role: выдаваемая роль в компании
    :param db: сессия
    :param cur_user: авторизованный пользователь
    :return: id клиента, выданному права администратора
    """
    # Проверка на корректность заданной роли
    if role not in CHANGEABLE_PORTAL_ROLES:
        raise HTTPException(status_code=422, detail='Incorrect static_data')
    # Проверка на возможность удаление авторизованным пользователем
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    is_permitted = await __check_permissions_granting_or_revoking_user_roles(cur_user_role_model, role, False)
    if not is_permitted:
        raise HTTPException(status_code=403, detail='Forbidden')
    if cur_user.user_id == demo_user_id:
        raise HTTPException(status_code=400, detail='Can not update privileges for itself')
    # Проверка на существование компании
    company_obj = await company.actions.__get_company_by_id(company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail=f'Company with id {company_id} not found')
    # Проверка на существование пользователя с ролью
    demo_user = await __get_user_by_id(user_id=demo_user_id, session=db)
    if demo_user is None:
        raise HTTPException(status_code=404, detail=f'User with id {demo_user_id} not found')
    demo_user_role_model = await __get_user_role_model(user_id=demo_user_id, session=db,
                                                       company_id=company_id)
    if not demo_user_role_model.check_existing_role(role):
        raise HTTPException(status_code=409, detail=f'User with id {demo_user_id} has no {role} privileges')
    demo_user_role_params = RevokeUserRoleRequest(user_id=demo_user_id,
                                                  company_id=company_id,
                                                  role=role)
    try:
        revoked_user_id = await __revoke_user_role(demo_user_role_params, db)
        if revoked_user_id is None:
            raise HTTPException(status_code=404,
                                detail=f'User with id {demo_user_id} with {role} in company with id {company_id} was '
                                       f'deleted')
        return RevokeUserRoleResponse(revoked_user_id=revoked_user_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')
