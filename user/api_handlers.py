import asyncio
from typing import Dict, List
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request
from auth.rate_limits import enforce_auth_limit
from bonuses.schemas import BonusEntryResponse
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from s3_directory.storage.s3client import S3Client
from user.actions import __create_user, __delete_user, __get_user_by_id, __update_user, \
    __check_user_permissions_on_delete, __check_user_permissions_on_update, \
    __generate_qr_base64, __verify_qr_token, \
    __get_user_staff_by_company_id, __get_search_users, __get_initial_search_users
from user.actions.get_current_user_from_token_action import __get_user_from_token, __get_user_by_email_for_auth
from user.interface_request import CreateUserRequest, UpdateUserRequest, UpdateBonusBalanceRequest
from user.interface_response import CreateUserResponse, DeleteUserResponse, GetUserResponse, UpdateUserResponse, \
    GetUserQrCodeResponse, GetUserQrPayloadResponse, UserWithRolesResponse, PaginatedUsersResponse

from db.session import get_db

from fastapi import APIRouter

from user_role.actions import __grant_user_role, __get_user_role_model
from user_role.interface_request import GrantUserRoleRequest
from utils.constants import BASE_STORAGE_DIRECTORY, PortalRole

user_router = APIRouter()

from pydantic import BaseModel
from user.account_status import AccountStatus


class AccountStatusChange(BaseModel):
    status: AccountStatus
    expected_status: AccountStatus


async def require_super_admin(actor, db):
    from user_role.actions import __is_exist_user_role
    from utils.constants import EMPTY_UUID
    if not await __is_exist_user_role(actor.user_id, EMPTY_UUID, PortalRole.PORTAL_ROLE_SUPER_ADMIN, db):
        raise HTTPException(403, 'Forbidden')


@user_router.get('/account_status')
async def get_account_status(user_id: UUID, db: AsyncSession = Depends(get_db),
                             actor: UserDB = Depends(__get_user_from_token)):
    await require_super_admin(actor, db)
    user = await __get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(404, 'User not found')
    return {'user_id': user.user_id, 'account_status': user.account_status}


@user_router.patch('/account_status')
async def change_account_status(user_id: UUID, body: AccountStatusChange,
                                db: AsyncSession = Depends(get_db),
                                actor: UserDB = Depends(__get_user_from_token)):
    from sqlalchemy import select
    from db import UserRoleDB
    await require_super_admin(actor, db)
    async with db.begin():
        target = await db.scalar(select(UserDB).where(UserDB.user_id == user_id).with_for_update(of=UserDB))
        if target is None:
            raise HTTPException(404, 'User not found')
        # Preserve the existing protection against removing superadmin access.
        protected = await db.scalar(select(UserRoleDB.user_id).where(UserRoleDB.user_id == user_id,
            UserRoleDB.role == PortalRole.PORTAL_ROLE_SUPER_ADMIN, UserRoleDB.is_active.is_(True)).limit(1))
        if user_id == actor.user_id or protected:
            raise HTTPException(403, 'Superadmin status cannot be changed via API')
        if target.account_status != body.expected_status:
            raise HTTPException(409, 'Account status changed; reload')
        target.account_status = body.status.value
        target.is_active = body.status not in (AccountStatus.blocked, AccountStatus.deleted)
        target.email_code_hash = None
        target.email_code_expires = None
        target.updater_id = actor.user_id
    return {'user_id': user_id, 'account_status': body.status}


@user_router.get('/bonus_history', response_model=List[BonusEntryResponse])
async def bonus_history(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                        db: AsyncSession = Depends(get_db),
                        current_user: UserDB = Depends(__get_user_from_token)):
    from sqlalchemy import select
    from db import BonusTransactionDB
    # Only the authenticated wallet; internal correction reasons/actors are not exposed.
    return (await db.scalars(select(BonusTransactionDB).where(
        BonusTransactionDB.user_id == current_user.user_id).order_by(
        BonusTransactionDB.created_at.desc(), BonusTransactionDB.transaction_id.desc())
        .limit(limit).offset(offset))).all()


@user_router.post("/create", response_model=CreateUserResponse)
async def create_user(body: CreateUserRequest, request: Request, db: AsyncSession = Depends(get_db)) -> CreateUserResponse:
    await enforce_auth_limit(request, db, str(body.email), registration=True)
    try:
        # User, welcome ledger, base role and QR commit together; S3 is not required.
        user = await __create_user(body, db)
        return user
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect static_data')


@user_router.delete("/delete", response_model=DeleteUserResponse)
async def delete_user(user_id: UUID,
                      db: AsyncSession = Depends(get_db),
                      current_user: UserDB = Depends(__get_user_from_token),
                      ) -> DeleteUserResponse:
    user_for_deletion = await __get_user_by_id(user_id=user_id, session=db)
    if user_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found'.format(user_id))
    # Проверка прав на удаление
    if not await __check_user_permissions_on_delete(
            target_user=user_for_deletion, current_user=current_user, db=db
    ):
        raise HTTPException(status_code=403, detail="Forbidden.")
    # Попытка удалить пользователя
    deleted_user_id = await __delete_user(user_id, db)
    if deleted_user_id is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} was deleted before'.format(user_id))
    return DeleteUserResponse(deleted_user_id=deleted_user_id)


@user_router.get('/get_by_id', response_model=GetUserResponse)
async def get_user_by_id(user_id: UUID,
                         db: AsyncSession = Depends(get_db),
                         current_user: UserDB = Depends(__get_user_from_token)) -> GetUserResponse:
    user = await __get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found or was deleted before'.format(user_id))
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    return user


@user_router.get('/check_by_email', response_model=Dict)
async def check_user_by_email(email: str, db: AsyncSession = Depends(get_db)) -> Dict:
    user = await __get_user_by_email_for_auth(email, db)
    if user is not None:
        raise HTTPException(status_code=404,
                            detail='User with email {0} already exists'.format(email))
    return {'Success': True}


@user_router.patch('/update_bonus_balance_by_id', response_model=UpdateUserResponse)
async def update_user_bonus_balance(user_id: UUID,
                                    body: UpdateBonusBalanceRequest,
                                    db: AsyncSession = Depends(get_db),
                                    current_user: UserDB = Depends(__get_user_from_token)) -> UpdateUserResponse:
    """Audited manual correction, not settlement of a check."""
    from bonuses.service import adjust_balance
    await adjust_balance(db, current_user.user_id, user_id, body)
    return UpdateUserResponse(updated_user_id=user_id)


@user_router.patch('/update_by_id', response_model=UpdateUserResponse)
async def update_user(user_id: UUID,
                      body: UpdateUserRequest,
                      db: AsyncSession = Depends(get_db),
                      current_user: UserDB = Depends(__get_user_from_token)) -> UpdateUserResponse:
    # Проверка на существование обновляемого пользователя
    user_for_update = await __get_user_by_id(user_id=user_id, session=db)
    if user_for_update is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found'.format(user_id))
    # Проверка прав на обновление
    if not await __check_user_permissions_on_update(target_user=user_for_update, current_user=current_user, db=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные пользователя
    update_user_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if 'email' in update_user_params and update_user_params['email'] != user_for_update.email:
        raise HTTPException(409, 'Email changes require a separate verification flow')
    # Пользователь не может самостоятельно обновлять свой баланс
    if 'bonus_balance' in update_user_params:
        raise HTTPException(status_code=403, detail='Forbidden')
    if update_user_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_user_id = await __update_user(update_user_params=update_user_params,
                                              user_id=user_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateUserResponse(updated_user_id=updated_user_id)


@user_router.get('/get_user_qr_code_by_id', response_model=GetUserQrCodeResponse)
async def get_user_qr_code_by_id(user_id: UUID,
                                 db: AsyncSession = Depends(get_db),
                                 current_user: UserDB = Depends(__get_user_from_token)) -> GetUserQrCodeResponse:
    user = await __get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found or was deleted before'.format(user_id))
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    return GetUserQrCodeResponse(qr_code=await asyncio.to_thread(__generate_qr_base64, str(user_id)))


@user_router.patch('/update_qr_code_by_id', response_model=GetUserQrCodeResponse)
async def update_qr_code_by_id(user_id: UUID,
                               db: AsyncSession = Depends(get_db),
                               current_user: UserDB = Depends(__get_user_from_token)) -> GetUserQrCodeResponse:
    user = await __get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found or was deleted before'.format(user_id))
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        # Создание qr кода
        qr_code = await asyncio.to_thread(__generate_qr_base64, str(user_id))
        return GetUserQrCodeResponse(qr_code=qr_code)
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect static_data')


class ScanClientQRRequest(BaseModel):
    qr_token: str
    company_id: UUID


@user_router.post("/scan_qr_code", response_model=GetUserQrPayloadResponse)
async def scan_qr_code(body: ScanClientQRRequest,
                       db: AsyncSession = Depends(get_db),
                       current_user: UserDB = Depends(__get_user_from_token)) -> GetUserQrPayloadResponse:
    from sqlalchemy import select
    from db import UserRoleDB, CompanyDB
    from user.account_status import require_confirmed
    async with db.begin():
        permitted = await db.scalar(select(UserRoleDB.user_id).join(CompanyDB, CompanyDB.company_id == UserRoleDB.company_id).where(
            UserRoleDB.user_id == current_user.user_id, UserRoleDB.company_id == body.company_id,
            UserRoleDB.is_active.is_(True), CompanyDB.is_active.is_(True),
            UserRoleDB.role.in_([PortalRole.PORTAL_ROLE_OWNER, PortalRole.PORTAL_ROLE_ADMIN, PortalRole.PORTAL_ROLE_WAITER])).limit(1))
        if not permitted:
            raise HTTPException(403, 'Forbidden')
        payload = await __verify_qr_token(body.qr_token)
        user = await db.scalar(select(UserDB).where(UserDB.user_id == UUID(payload['user_id'])))
        if user is None:
            raise HTTPException(404, 'Client not found')
        require_confirmed(user)
        return GetUserQrPayloadResponse(user_id=user.user_id, exp=payload['exp'])


@user_router.get("/get_employees", response_model=List[UserWithRolesResponse],
                 summary="Получить сотрудников компании",
                 description="Возвращает информацию о всех сотрудниках в указанной компании с их ролями")
async def get_company_employees(company_id: UUID,
                                db: AsyncSession = Depends(get_db),
                                current_user: UserDB = Depends(__get_user_from_token)):
    """
    Получить всех сотрудников компании с их ролями.
    """
    # Проверка прав на получение информации о заказе сотрудником
    cur_user_role_model = await __get_user_role_model(user_id=current_user.user_id, session=db,
                                                      company_id=company_id)
    if len(cur_user_role_model.user_roles) > 0:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Находим всех пользователей, у которых есть роли в указанной компании
    users = await __get_user_staff_by_company_id(company_id, db)
    return users


@user_router.get("/get_all_users_by",
                 response_model=PaginatedUsersResponse,
                 summary="Получить пользователей для выдачи/отзыва ролей",
                 description="""Возвращает список пользователей в двух кейсах:
                                1) Сначала первые 100 юзеров: сотрудники компании админа + последние зарегистрированные.
                                2) Затем используя параметр search находим подходящие""")
async def get_users_for_admin(company_id: UUID,
                              search: str = '',
                              offset: int = 0,
                              db: AsyncSession = Depends(get_db),
                              current_user: UserDB = Depends(__get_user_from_token)):

    # Проверка прав на получение информации о заказе сотрудником
    cur_user_role_model = await __get_user_role_model(user_id=current_user.user_id, session=db,
                                                      company_id=company_id)
    if not(cur_user_role_model.is_owner or cur_user_role_model.is_admin):
        raise HTTPException(status_code=403, detail='Forbidden')
    if search:
        # Поиск по строке поиска
        return await __get_search_users(search, company_id, db)
    else:
        # Первоначальный запрос: сотрудники компании + последние пользователи
        return await __get_initial_search_users(company_id, db)
