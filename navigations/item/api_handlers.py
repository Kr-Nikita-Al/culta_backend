from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from navigations.item.actions import __create_item, __get_item_by_id
from navigations.item.interface_request import CreateItemRequest
from navigations.item.interface_response import CreateItemResponse, GetItemResponse

item_router = APIRouter()


@item_router.post('/create', response_model=CreateItemResponse)
async def create_item(body: CreateItemRequest,
                      db: AsyncSession = Depends(get_db)) -> CreateItemResponse:
    return await __create_item(body, db)


@item_router.get('/get_by_id', response_model=GetItemResponse)
async def get_item_by_id(item_id: UUID, db: AsyncSession = Depends(get_db)) -> GetItemResponse:
    item = await __get_item_by_id(item_id, db)
    if item is None:
        raise HTTPException(status_code=404,
                            detail='Item with id {0} is not found or was deleted before'.format(item_id))
    return item

