from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from user.actions import _create_user, _delete_user, _get_user_by_id, \
    _update_user
from user.interfaces_request import CreateUserRequest, UpdateUserRequest
from user.interfaces_response import CreateUserResponse, DeleteUserResponse, \
    GetUserResponse, UpdateUserResponse


from db.session import get_db

from fastapi import APIRouter


user_router = APIRouter()

@user_router.post("/create", response_model=CreateUserResponse)
async def create_user(body: CreateUserRequest, db: AsyncSession = Depends(get_db)) -> CreateUserResponse:
    return await _create_user(body, db)


@user_router.delete("/delete", response_model=DeleteUserResponse)
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_db)) -> DeleteUserResponse:
    user_for_deletion = await _get_user_by_id(user_id=user_id, session=db)
    if user_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found'.format(user_id))
    # Попытка удалить пользователя
    deleted_user_id = await _delete_user(user_id, db)
    if deleted_user_id is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} was deleted before'.format(user_id))
    return DeleteUserResponse(deleted_user_id=deleted_user_id)


@user_router.get('/get_by_id', response_model=GetUserResponse)
async def get_user_by_id(user_id: UUID, db: AsyncSession = Depends(get_db)) -> GetUserResponse:
    user = await _get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found or was deleted before'.format(user_id))
    return user


@user_router.patch('/update_by_id', response_model=UpdateUserResponse)
async def update_user(user_id: UUID,
                               body: UpdateUserRequest,
                               db: AsyncSession = Depends(get_db)) -> UpdateUserResponse:
    # Проверка на существование обновляемого пользователя
    user_for_update = await _get_user_by_id(user_id=user_id, session=db)
    if user_for_update is None:
        raise HTTPException(status_code=404,
                            detail='User with id {0} is not found'.format(user_id))
    # Попытка обновить данные пользователя
    update_user_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    if update_user_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_user_id = await _update_user(updated_user_params=update_user_params,
                                                         user_id=user_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateUserResponse(updated_User_id=updated_user_id)