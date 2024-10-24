from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from navigations.item.actions import __create_item, __get_item_by_id, __delete_item, __update_item_by_id
from navigations.item.interface_request import CreateItemRequest, UpdateItemRequest
from navigations.item.interface_response import CreateItemResponse, GetItemResponse, DeleteItemResponse, UpdateItemResponse

item_router = APIRouter()


@item_router.post('/create', response_model=CreateItemResponse)
async def create_item(body: CreateItemRequest,
                      db: AsyncSession = Depends(get_db)) -> CreateItemResponse:
    return await __create_item(body, db)


@item_router.get('/get_by_id', response_model=GetItemResponse)
async def get_item_by_id(item_id: UUID, db: AsyncSession = Depends(get_db)) -> GetItemResponse:
    item = await __get_item_by_id(item_id=item_id, session=db)
    if item is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found or was deleted before'.format(item_id))
    return item


@item_router.delete("/delete", response_model=DeleteItemResponse)
async def delete_item(item_id: UUID, db: AsyncSession = Depends(get_db)) -> DeleteItemResponse:
    item_for_deletion = await __get_item_by_id(item_id=item_id, session=db)
    if item_for_deletion is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found'.format(item_id))
    # Попытка удалить item
    deleted_item_id = await __delete_item(item_id, db)
    if deleted_item_id is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} was deleted before'.format(deleted_item_id))
    return DeleteItemResponse(deleted_item_id=deleted_item_id)


@item_router.patch('/update_by_id', response_model=UpdateItemResponse)
async def update_item_by_id(item_id: UUID,
                            body: UpdateItemRequest,
                            db: AsyncSession = Depends(get_db)) -> UpdateItemResponse:
    # Проверка на существование обновляемый item
    item_for_update = await __get_item_by_id(item_id=item_id, session=db)
    if item_for_update is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found'.format(item_id))
    # Попытка обновить данные item
    update_item_params = body.dict(exclude_none=True)
    if update_item_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        updated_item_id = await __update_item_by_id(update_item_params=update_item_params,
                                                    item_id=item_id, session=db)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateItemResponse(updated_item_id=updated_item_id)
