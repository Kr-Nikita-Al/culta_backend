from uuid import UUID

from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB, STATUS_TYPE, STATUS_VALUES
from db.session import get_db
from sqlalchemy.exc import DBAPIError, IntegrityError

from order.actions import __create_order, __check_permissions_create_order, __get_order_by_id, __get_orders, \
    __check_permissions_update_status, __update_order_by_id
from order.interface_request import CreateOrderRequest, UpdateOrderRequest
from order.interface_response import CreateOrderResponse, GetOrderResponse, GetOrdersResponse, UpdateOrderResponse
from order.order_product_association.actions import __create_order_product_action, __update_order_product_action
from order.order_product_association.interface_request import CreateOrderProductRequest
from order.websocket import order_manager
from user.actions import __get_user_from_token, __get_user_by_id
from user_role.actions import __get_user_role_model

order_router = APIRouter()


@order_router.post("/create", response_model=CreateOrderResponse)
async def create_order(body: CreateOrderRequest,
                       db: AsyncSession = Depends(get_db),
                       cur_user: UserDB = Depends(__get_user_from_token)) -> CreateOrderResponse:
    """
    TODO: в момент создания заказа либо создавать новый чек, либо прикреплять к существующему незакрытому

    :param body:
    :param db:
    :param cur_user:
    :return:
    """
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
        # Уведомляем о новом заказе
        await order_manager.broadcast_to_waiters({"type": "new_order", "order": order.dict()})
        return order
    except DBAPIError as e:
        raise HTTPException(status_code=422, detail='Incorrect static_data')


@order_router.get('/get_by_id', response_model=GetOrderResponse)
async def get_order_by_id(order_id: UUID,
                          db: AsyncSession = Depends(get_db),
                          cur_user: UserDB = Depends(__get_user_from_token),
                          company_id: UUID = None) -> GetOrderResponse:
    is_staff: bool = company_id is not None
    if is_staff:
        company = await __get_company_by_id(company_id, db)
        if company is None:
            raise HTTPException(status_code=404,
                                detail='Company with id {0} is not found or was deleted before'.format(company_id))
        # Проверка прав на получение информации о заказе сотрудником
        cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                          company_id=company_id)
        if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or
                cur_user_role_model.is_waiter or cur_user_role_model.is_cook):
            raise HTTPException(status_code=403, detail='Forbidden')
    order = await __get_order_by_id(order_id, is_staff, db)
    # Проверка прав на получение информации о заказе обычным юзером
    if not is_staff and order.user_id != cur_user.user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    if order is None:
        raise HTTPException(status_code=404, detail='Order with id {0} is not found'.format(order_id))
    return order


@order_router.get('/get_all', response_model=GetOrdersResponse)
async def get_all(company_id: UUID = None,
                  filter_status_str: str = '',
                  db: AsyncSession = Depends(get_db),
                  cur_user: UserDB = Depends(__get_user_from_token)) -> GetOrdersResponse:
    filter_status_list = []
    if len(filter_status_str) != 0:
        filter_status_list = filter_status_str.split(',') if ',' in filter_status_str else [filter_status_str]
        if not all(item in STATUS_VALUES for item in filter_status_list):
            raise HTTPException(status_code=422, detail='Incorrect statuses')
        filter_status_list = [STATUS_TYPE(item) for item in filter_status_list]
    is_staff: bool = company_id is not None
    if is_staff:
        company = await __get_company_by_id(company_id, db)
        if company is None:
            raise HTTPException(status_code=404,
                                detail='Company with id {0} is not found or was deleted before'.format(company_id))
        # Проверка прав на получение информации о заказе сотрудником
        cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                          company_id=company_id)
        if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or
                cur_user_role_model.is_waiter or cur_user_role_model.is_cook):
            raise HTTPException(status_code=403, detail='Forbidden')
    orders = await __get_orders(is_staff=is_staff, session=db, user_id=cur_user.user_id,
                                statuses=filter_status_list, company_id=company_id)
    return orders


@order_router.patch('/update_status_by_id', response_model=UpdateOrderResponse)
async def update_status_by_id(order_id: UUID,
                              new_status: STATUS_TYPE,
                              db: AsyncSession = Depends(get_db),
                              cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateOrderResponse:
    """
    TODO: закрывать чек сразу после закрытия заказа в рамках компаний с самообслуживанием
    :param order_id:
    :param new_status:
    :param db:
    :param cur_user:
    :return:
    """
    # Проверка на существование обновляемого заказа
    order = await __get_order_by_id(order_id, True, db)
    if order is None:
        raise HTTPException(status_code=404,
                            detail='Order with id {0} is not found'.format(order_id))
    # Проверка прав на получение информации о заказе сотрудником
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=order.company_id)
    # Проверка прав на обновление статуса
    if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or
            cur_user_role_model.is_waiter or cur_user_role_model.is_cook):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка корректность обновления статуса
    if not await __check_permissions_update_status(user_role_model=cur_user_role_model,
                                             old_status=order.status,
                                             new_status=new_status):
        raise HTTPException(status_code=422, detail='Incorrect new status for update')
    try:
        upd_order_params = {'status': new_status, 'updater_id': cur_user.user_id}
        updated_order_id = await __update_order_by_id(update_order_params=upd_order_params,
                                                      order_id=order_id, session=db)
        # Уведомляем об обновлении через WebSocket
        updated_order = await __get_order_by_id(order_id, True, db)
        await order_manager.notify_order_update(updated_order_id, {"type": "order_updated", "order": updated_order.dict()})
        return UpdateOrderResponse(updated_order_id=updated_order_id)
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')


@order_router.patch('/update_by_id', response_model=UpdateOrderResponse)
async def update_order_by_id(order_id: UUID,
                             body: UpdateOrderRequest,
                             db: AsyncSession = Depends(get_db),
                             cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateOrderResponse:
    # Проверка, что не пытается обновиться статус
    if 'status' in body.dict().keys():
        raise HTTPException(status_code=422, detail='Incorrect api for status update')
    # Проверка прав на обновление данных
    order = await __get_order_by_id(order_id, True, db)
    if order is None:
        raise HTTPException(status_code=404,
                            detail='Order with id {0} is not found'.format(order_id))
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id,
                                                      session=db,
                                                      company_id=order.company_id)
    # Проверка прав на обновление заказа
    if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or
            cur_user_role_model.is_waiter or cur_user_role_model.is_cook):
        raise HTTPException(status_code=403, detail='Forbidden')
    # Попытка обновить данные компании
    upd_order_params = body.dict(exclude_none=True)
    if upd_order_params == {}:
        raise HTTPException(status_code=422, detail='All fields are empty')
    try:
        upd_order_params['updater_id'] = cur_user.user_id
        if body.order_items is not None and len(body.order_items) > 0:
            for order_item in body.order_items:
                if await __update_order_product_action(order_id=order.order_id,
                                                       product_card_id=order_item.product_card_id,
                                                       update_order_product_params={'quantity': order_item.quantity},
                                                       session=db) is None:
                    raise HTTPException(status_code=404,
                                        detail='Product card with id {0} is not found in order' \
                                        .format(order_item.product_card_id))
            del upd_order_params["order_items"]
        updated_order_id = await __update_order_by_id(update_order_params=upd_order_params,
                                                      order_id=order_id, session=db)
        # Уведомляем об обновлении через WebSocket
        updated_order = await __get_order_by_id(order_id, True, db)
        await order_manager.notify_order_update(updated_order_id,
                                                {"type": "order_updated", "order": updated_order.dict()})
        if updated_order_id is None:
            raise HTTPException(status_code=404,
                                detail='Order with id {0} not existed or was closed/canceled'.format(order_id))
    except IntegrityError as e:
        raise HTTPException(status_code=503, detail='Database error')
    return UpdateOrderResponse(updated_order_id=updated_order_id)
