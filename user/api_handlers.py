from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB
from user.actions import __create_user, __delete_user, __get_user_by_id, __update_user, \
    __check_user_permissions_on_delete, __check_user_permissions_on_update
from user.actions.get_current_user_from_token_action import __get_user_from_token, __get_user_by_email_for_auth
from user.interface_request import CreateUserRequest, UpdateUserRequest
from user.interface_response import CreateUserResponse, DeleteUserResponse, GetUserResponse, UpdateUserResponse

from db.session import get_db

from fastapi import APIRouter

user_router = APIRouter()


@user_router.post("/create", response_model=CreateUserResponse)
async def create_user(body: CreateUserRequest, db: AsyncSession = Depends(get_db)) -> CreateUserResponse:
    try:
        return await __create_user(body, db)
    except DBAPIError as e:
        raise HTTPException(status_code=422,
                            detail='Incorrect data')


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
    if not __check_user_permissions_on_delete(
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
async def get_user_by_id(user_id: UUID, db: AsyncSession = Depends(get_db)) -> GetUserResponse:
    user = await __get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found or was deleted before'.format(user_id))
    return user


@user_router.get('/check_by_email')
async def check_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    user = await __get_user_by_email_for_auth(email, db)
    if user is not None:
        raise HTTPException(status_code=404,
                            detail='User with email {0} already exists'.format(email))
    return {'Success': True}


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
    if not __check_user_permissions_on_update(
            target_user=user_for_update, current_user=current_user, db=db):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные пользователя
    update_user_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if update_user_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_user_id = await __update_user(update_user_params=update_user_params,
                                              user_id=user_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateUserResponse(updated_user_id=updated_user_id)
