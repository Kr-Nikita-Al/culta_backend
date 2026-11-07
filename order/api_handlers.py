import logging
from typing import List, Optional
from pydantic import constr
from sqlalchemy import select
from db import OrderStatusHistoryDB
from order.interface_response.status_history_response import StatusHistoryResponse
from uuid import UUID

from fastapi import Depends, HTTPException, APIRouter, Response
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB, STATUS_TYPE, STATUS_VALUES
from db.session import get_db
from sqlalchemy.exc import DBAPIError, DataError, IntegrityError, InterfaceError, OperationalError

from order.actions import __create_order, __check_permissions_create_order, __get_order_by_id, __get_orders, \
    __update_order_by_id
from order.status_policy import validate_transition
from order.interface_request import CreateOrderRequest, UpdateOrderRequest
from order.interface_response import CreateOrderResponse, GetOrderResponse, GetOrdersResponse, UpdateOrderResponse
from order.websocket import order_manager
from user.actions import __get_user_from_token, __get_user_by_id
from user_role.actions import __get_user_role_model

logger = logging.getLogger(__name__)


class OrderRoute(APIRoute):
    """Translate database failures without exposing SQL or driver messages."""

    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def handle_request(request):
            try:
                return await route_handler(request)
            except IntegrityError as exc:
                raise HTTPException(status_code=409, detail='Order data conflict') from exc
            except DataError as exc:
                raise HTTPException(status_code=422, detail='Invalid order data') from exc
            except (OperationalError, InterfaceError) as exc:
                logger.exception('Order database is unavailable')
                raise HTTPException(status_code=503, detail='Database unavailable') from exc
            except DBAPIError as exc:
                logger.exception('Unexpected order database error')
                raise HTTPException(status_code=500, detail='Internal database error') from exc

        return handle_request


from company.modules import module_guard
order_router = APIRouter(route_class=OrderRoute, dependencies=[Depends(module_guard('orders'))])

from order.client_schemas import ClientOrderRequest, ClientOrderResponse, TableQRRequest, ResolveTableRequest
from order import client_service


@order_router.post('/table-qr')
async def issue_table_qr(body: TableQRRequest, response: Response, db: AsyncSession = Depends(get_db),
                         actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        response.headers['Cache-Control'] = 'no-store'
        return await client_service.issue_table_qr(db, body, actor)


@order_router.post('/resolve-table')
async def resolve_table(body: ResolveTableRequest, db: AsyncSession = Depends(get_db),
                        actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        await client_service.active_actor(db, actor.user_id)
        company = await client_service.active_company(db, body.company_id)
        table = await client_service.resolve_table(db, body.company_id, body.table_token)
        return {'company_id': company.company_id, 'company_name': company.company_name,
                'table_id': table.table_id, 'table_label': table.label,
                'can_order': bool(company.work_state and company.allow_client_orders_inside)}


@order_router.post('/create-client', response_model=ClientOrderResponse)
async def create_client_order(body: ClientOrderRequest, db: AsyncSession = Depends(get_db),
                               actor: UserDB = Depends(__get_user_from_token)):
    order_body = CreateOrderRequest(company_id=body.company_id, user_id=actor.user_id,
        check_id=body.check_id, comment=body.comment, cocking_time=0, order_items=body.order_items)
    order = await __create_order(order_body, actor.user_id, db, client_request=body)
    if not order.replayed:
        await _notify_new_order(order)
    return order


async def _notify_new_order(order: CreateOrderResponse):
    # The legacy global broadcast includes employees of other companies.
    broadcast = getattr(order_manager, 'broadcast_to_company', None)
    if broadcast is None:
        logger.warning('Company-scoped order notifier is unavailable; order_id=%s', order.order_id)
        return
    try:
        await broadcast(order.company_id, {"type": "new_order", "order": jsonable_encoder(order)})
    except Exception:
        logger.exception('New order notification failed; order_id=%s', order.order_id)


async def _notify_order_updated(order_id: UUID, db: AsyncSession):
    """Notification failures must not turn an already committed PATCH into a 500."""
    notify = getattr(order_manager, 'notify_order_update', None)
    if notify is None:
        logger.warning('Order update notifier is unavailable; order_id=%s', order_id)
        return
    try:
        updated_order = await __get_order_by_id(order_id, True, db)
        if updated_order is None:
            logger.warning('Order disappeared before notification; order_id=%s', order_id)
            return
        await notify(order_id, {"type": "order_updated", "order": jsonable_encoder(updated_order)})
    except Exception:
        logger.exception('Order update notification failed; order_id=%s', order_id)


@order_router.post("/create", response_model=CreateOrderResponse)
async def create_order(body: CreateOrderRequest,
                       db: AsyncSession = Depends(get_db),
                       cur_user: UserDB = Depends(__get_user_from_token)) -> CreateOrderResponse:
    """
    Создаёт заказ и новый чек либо добавляет заказ в открытый чек официанта.

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
    user_obj = await __get_user_by_id(body.user_id, db) if body.user_id else None
    staff_obj = await __get_user_by_id(cur_user.user_id, db)
    if body.user_id is not None and user_obj is None:
        raise HTTPException(status_code=404, detail=f'User with id {body.user_id} not found')
    if staff_obj is None:
        raise HTTPException(status_code=404, detail=f'Staff with id {cur_user.user_id} not found')
    order = await __create_order(body, cur_user.user_id, db)
    await _notify_new_order(order)
    return order


@order_router.get('/get_by_id', response_model=GetOrderResponse)
async def get_order_by_id(order_id: UUID,
                          db: AsyncSession = Depends(get_db),
                          cur_user: UserDB = Depends(__get_user_from_token),
                          company_id: UUID = None, include_cost: bool = True) -> GetOrderResponse:
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
    can_view_cost = is_staff and include_cost and (cur_user_role_model.is_admin or cur_user_role_model.is_owner)
    order = await __get_order_by_id(order_id, is_staff, db, include_cost=can_view_cost)
    if order is None:
        raise HTTPException(status_code=404, detail='Order with id {0} is not found'.format(order_id))
    if is_staff and order.company_id != company_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    # Проверка прав на получение информации о заказе обычным юзером
    if not is_staff and order.user_id != cur_user.user_id:
        raise HTTPException(status_code=403, detail='Forbidden')
    return order


@order_router.get('/get_all', response_model=GetOrdersResponse)
async def get_all(company_id: UUID = None,
                  filter_status_str: str = '',
                  include_cost: bool = True,
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
                                statuses=filter_status_list, company_id=company_id,
                                include_cost=is_staff and include_cost and (cur_user_role_model.is_admin or cur_user_role_model.is_owner))
    return orders


@order_router.patch('/update_status_by_id', response_model=UpdateOrderResponse)
async def update_status_by_id(order_id: UUID,
                              new_status: STATUS_TYPE,
                              db: AsyncSession = Depends(get_db),
                              cur_user: UserDB = Depends(__get_user_from_token),
                              reason: Optional[constr(strip_whitespace=True, max_length=500)] = None) -> UpdateOrderResponse:
    """
    Меняет готовность заказа. Оплата и закрытие чека выполняются отдельно.
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
    validate_transition(cur_user_role_model, order.status, new_status,
                        check_id=getattr(order, 'check_id', None))
    upd_order_params = {'status': new_status, 'updater_id': cur_user.user_id}
    updated_order_id = await __update_order_by_id(update_order_params=upd_order_params,
                                                 order_id=order_id, session=db,
                                                 expected_status=order.status,
                                                 status_reason=reason or None)
    if updated_order_id is None:
        raise HTTPException(status_code=409, detail='Order changed; reload and retry')
    await _notify_order_updated(updated_order_id, db)
    return UpdateOrderResponse(updated_order_id=updated_order_id)


@order_router.get('/status_history', response_model=List[StatusHistoryResponse])
async def get_status_history(order_id: UUID, company_id: UUID,
                             db: AsyncSession = Depends(get_db),
                             cur_user: UserDB = Depends(__get_user_from_token)):
    # Reuse staff/company authorization. Internal reasons and actor IDs are not
    # included in customer DTOs or socket broadcasts.
    await get_order_by_id(order_id=order_id, company_id=company_id, db=db, cur_user=cur_user)
    async with db.begin():
        result = await db.execute(select(OrderStatusHistoryDB).where(
            OrderStatusHistoryDB.order_id == order_id).order_by(
            OrderStatusHistoryDB.changed_at, OrderStatusHistoryDB.event_id))
        return [StatusHistoryResponse.from_orm(row) for row in result.scalars().all()]


@order_router.patch('/update_by_id', response_model=UpdateOrderResponse)
async def update_order_by_id(order_id: UUID,
                             body: UpdateOrderRequest,
                             db: AsyncSession = Depends(get_db),
                             cur_user: UserDB = Depends(__get_user_from_token)) -> UpdateOrderResponse:
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
    if order.status in (STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED):
        raise HTTPException(status_code=409, detail='Order is closed or canceled')
    upd_order_params = body.dict(exclude_none=True, exclude={'order_items'})
    # An empty list is a no-op, not a column to pass to SQLAlchemy UPDATE.
    if not upd_order_params and not body.order_items:
        raise HTTPException(status_code=422, detail='All fields are empty')
    upd_order_params['updater_id'] = cur_user.user_id
    updated_order_id = await __update_order_by_id(update_order_params=upd_order_params,
                                                 order_id=order_id, session=db,
                                                 order_items=body.order_items,
                                                 expected_status=order.status)
    if updated_order_id is None:
        raise HTTPException(status_code=409, detail='Order changed; reload and retry')
    await _notify_order_updated(updated_order_id, db)
    return UpdateOrderResponse(updated_order_id=updated_order_id)
