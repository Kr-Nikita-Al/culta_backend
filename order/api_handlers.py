from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB
from db.session import get_db
from fastapi import APIRouter
from sqlalchemy.exc import IntegrityError, DBAPIError

from order.actions import __create_order, __check_permissions_create_order, __get_order_by_id
from order.interface_request import CreateOrderRequest
from order.interface_response import CreateOrderResponse, GetOrderResponse, \
    GetClientOrderResponse, GetStaffOrderResponse
from order.order_product_association.actions import __create_order_product_action
from order.order_product_association.interface_request import CreateOrderProductRequest
from user.actions import __get_user_from_token, __get_user_by_id
from user_role.actions import __get_user_role_model
from utils.constants import EMPTY_UUID

order_router = APIRouter()


@order_router.post("/create", response_model=CreateOrderResponse)
async def create_order(body: CreateOrderRequest,
                       db: AsyncSession = Depends(get_db),
                       cur_user: UserDB = Depends(__get_user_from_token)) -> CreateOrderResponse:
    # Проверка прав на создание
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=body.company_id)
    if not await __check_permissions_create_order(cur_user_role_model):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка на существование компании
    company_obj = await __get_company_by_id(body.company_id, db)
    if company_obj is None:
        raise HTTPException(status_code=404, detail=f'Company with id {body.company_id} not found')
    # Проверка на существование сотрудника и клиента в БД
    user_obj = await __get_user_by_id(body.user_id, db)
    staff_obj = await __get_user_by_id(cur_user.user_id, db)
    if user_obj is None:
        raise HTTPException(status_code=404, detail=f'User with id {body.user_id} not found')
    if staff_obj is None:
        raise HTTPException(status_code=404, detail=f'Staff with id {cur_user.user_id} not found')
    try:
        order = await __create_order(body, cur_user.user_id, db)
        if body.order_items is not None and len(body.order_items) > 0:
            for order_item in body.order_items:
                await __create_order_product_action(
                                CreateOrderProductRequest(order_id=order.order_id,
                                                          product_card_id=order_item.product_card_id,
                                                          quantity=order_item.quantity),
                                db)
        return order
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect data')


@order_router.get('/get_by_id', response_model=GetOrderResponse)
async def get_order_by_id(order_id: UUID,
                          db: AsyncSession = Depends(get_db),
                          cur_user: UserDB = Depends(__get_user_from_token),
                          company_id: UUID = EMPTY_UUID) -> GetOrderResponse:
    is_staff: bool = company_id != EMPTY_UUID
    if is_staff:
        # Проверка прав на получение информации о заказе сотрудником
        cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                          company_id=company_id)
        if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or cur_user_role_model.is_waiter):
            raise HTTPException(status_code=403, detail='Forbidden')
    order = await __get_order_by_id(order_id, is_staff, db)
    # Проверка прав на получение информации о заказе обычным юзером
    if not is_staff and order.user_id != cur_user.user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    if order is None:
        raise HTTPException(status_code=404, detail='Order with id {0} is not found'.format(order_id))
    return order



# @order_router.get('/get_all', response_model=GetAllOrderResponse)
# async def get_all_companies(company_id: UUID,
#                             db: AsyncSession = Depends(get_db),
#                             cur_user: UserDB = Depends(__get_user_from_token)) -> GetAllOrderResponse:
#     cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
#                                                       company_id=company_id)
#     if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or cur_user_role_model.is_waiter):
#         raise HTTPException(status_code=403, detail='Forbidden')
#     orders = await __get_all_orders(company_id, db)
#     if orders is None:
#         raise HTTPException(status_code=404,
#                             detail='Table Company is empty')
#     return GetAllOrderResponse(orders=orders)


# @order_router.patch('/update_by_id', response_model=UpdateOrderResponse)
# async def update_company_by_id(order_id: UUID,
#                                body: UpdateOrderRequest,
#                                db: AsyncSession = Depends(get_db),
#                                cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateOrderResponse:
#     # # Проверка прав на обновление данных
    # cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db, company_id=company_id)
    # if not cur_user_role_model.is_admin and not cur_user_role_model.is_super_admin:
    #     raise HTTPException(status_code=403, detail='Forbidden')
    # # Проверка на существование обновляемой компании
    # upd_company = await __get_company_by_id(company_id=company_id, session=db)
    # if upd_company is None:
    #     raise HTTPException(status_code=404,
    #                         detail='Company with id {0} is not found'.format(company_id))
    # # Попытка обновить данные компании
    # upd_company_params = body.dict(exclude_none=True)  # exclude_none, чтобы удалить незаполненные поля
    # if upd_company_params == {}:
    #     raise HTTPException(status_code=422, detail='All fields are empty')
    # try:
    #     upd_company_params['updater_id'] = cur_user.user_id
    #     updated_company_id = await __update_company_by_id(update_company_params=upd_company_params,
    #                                                       company_id=company_id, session=db)
    #     # Обновление статуса изображений в случае наличия их в upd_company_params
    #     images_upd_dict = {upd_company.__getattribute__(img_id): upd_company_params[img_id] for img_id in
    #                        ['image_picture_id', 'image_icon_id'] if img_id in upd_company_params.keys()}
    #     if images_upd_dict != {}:
    #         await __update_status_used_image(images_upd_dict=images_upd_dict, session=db)
    # except IntegrityError as e:
    #     raise HTTPException(status_code=503, detail='Database error')
    # if updated_company_id is None:
    #     raise HTTPException(status_code=404,  detail='Company with id {0} was deleted'.format(company_id))
    # return UpdateOrderResponse(updated_order_id=updated_order_id)
