import asyncio
from typing import Dict, List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from db import UserDB
from s3_directory.storage.s3client import S3Client
from user.actions import __create_user, __delete_user, __get_user_by_id, __update_user, \
    __check_user_permissions_on_delete, __check_user_permissions_on_update, \
    __check_user_permissions_on_update_bonus_balance, __generate_qr_base64, __verify_qr_token, \
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


@user_router.post("/create", response_model=CreateUserResponse)
async def create_user(body: CreateUserRequest, db: AsyncSession = Depends(get_db)) -> CreateUserResponse:
    try:
        # Создания пользователя в БД
        user = await __create_user(body, db)
        # Создания папки в s3 storage
        s3client = S3Client()
        await s3client.create_directory(dir_path=BASE_STORAGE_DIRECTORY.USER,
                                        dir_name="user_{0}".format(str(user.user_id)))
        # Выделения прав пользователя
        _ = await __grant_user_role(GrantUserRoleRequest(user_id=user.user_id,
                                                         role=PortalRole.PORTAL_ROLE_USER,
                                                         creator_id=user.user_id), db)
        # Создание qr кода
        qr_code = await asyncio.to_thread(__generate_qr_base64, str(user.user_id))
        _ = await __update_user(update_user_params={'qr_code': qr_code},
                                user_id=user.user_id, session=db)
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
    """
      TODO: добавить возможность обновления бонусного счета только в рамках закрытого сегодняшнего заказа
      :param user_id:
      :param db:
      :param body:
      :param current_user:
      :return:
      """
    # Проверка на существование пользователя
    user_for_update = await __get_user_by_id(user_id=user_id, session=db)
    if user_for_update is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found'.format(user_id))
    # Проверка прав на обновление
    if not await __check_user_permissions_on_update_bonus_balance(target_user=user_for_update,
                                                                  is_write_off=bool(body.is_write_off),
                                                                  company_id=body.company_id,
                                                                  current_user=current_user, db=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    update_user_params = {'bonus_balance': user_for_update.bonus_balance}
    if body.is_write_off:
        if (update_user_params['bonus_balance'] - body.amount) < 0:
            raise HTTPException(status_code=422, detail='Incorrect static_data')
        update_user_params['bonus_balance'] -= body.amount
    else:
        update_user_params['bonus_balance'] += body.amount
    try:
        updated_user_id = await __update_user(update_user_params=update_user_params,
                                              user_id=user_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateUserResponse(updated_user_id=updated_user_id)


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
    return GetUserQrCodeResponse(qr_code=user.qr_code)


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
        _ = await __update_user(update_user_params={'qr_code': qr_code},
                                user_id=user.user_id, session=db)
        return GetUserQrCodeResponse(qr_code=user.qr_code)
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect static_data')


@user_router.post("/scan_qr_code", response_model=GetUserQrPayloadResponse)
async def scan_qr_code(qr_token: str,
                       company_id: UUID,
                       db: AsyncSession = Depends(get_db),
                       current_user: UserDB = Depends(__get_user_from_token)) -> GetUserQrPayloadResponse:
    # Проверка прав
    user_role_model = await __get_user_role_model(user_id=current_user.user_id, session=db,
                                                  company_id=company_id)
    if not(user_role_model.is_owner or user_role_model.is_admin or user_role_model.is_waiter):
        raise HTTPException(status_code=403, detail='Forbidden')
    try:
        # Проверка qr_token и user_id
        payload = await __verify_qr_token(qr_token)
        user_id = payload.get('user_id')
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid QR code: no user_id found")
        exp = payload.get('exp')
        user = await __get_user_by_id(user_id, db)
        return GetUserQrPayloadResponse(user_id=user.user_id, exp=exp)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing QR code: {str(e)}")


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

