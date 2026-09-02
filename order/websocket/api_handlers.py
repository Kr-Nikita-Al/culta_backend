from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import OrderDB, UserDB
from db.session import get_db
from order.websocket import order_manager
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model

order_websocket_router = APIRouter()


# Для staff
@order_websocket_router.websocket("/orders/ws/staff")
async def waiter_orders_websocket(
        websocket: WebSocket,
        company_id: UUID,
        db: AsyncSession = Depends(get_db),
        cur_user: UserDB = Depends(__get_user_from_token)
):
    # Проверка прав на получение информации о заказе сотрудником
    cur_user_role_model = await __get_user_role_model(user_id=cur_user.user_id, session=db,
                                                      company_id=company_id)
    # Проверка прав
    if not (cur_user_role_model.is_admin or cur_user_role_model.is_owner or
            cur_user_role_model.is_waiter or cur_user_role_model.is_cook):
        raise HTTPException(status_code=403, detail='Forbidden')

    connection = await order_manager.connect_waiter(websocket)

    try:
        while True:
            # Официант может отправлять команды на изменение статуса
            data = await websocket.receive_json()

            if data.get("type") == "update_status":
                order_id = data["order_id"]
                new_status = data["status"]

                # Обновляем статус в БД
                async with AsyncSessionLocal() as session:
                    order = await session.get(OrderDB, order_id)
                    order.status = new_status
                    await session.commit()

                # Уведомляем всех официантов и клиента
                await order_manager.broadcast_to_waiters({
                    "type": "order_updated",
                    "order_id": order_id,
                    "status": new_status
                })

                # Уведомляем клиента
                await order_manager.send_to_order(order_id, {
                    "type": "status_changed",
                    "status": new_status,
                    "order_id": order_id
                })

                # Если заказ завершен, закрываем соединения клиента
                if new_status in ["completed", "cancelled"]:
                    await order_manager.send_to_order(order_id, {
                        "type": "order_finished",
                        "status": new_status,
                        "message": "Заказ завершен"
                    })
                    # Закрываем соединения клиента
                    if order_id in order_manager.order_connections:
                        for conn in list(order_manager.order_connections[order_id]):
                            await conn.close(code=1000)

    except WebSocketDisconnect:
        await order_manager.disconnect_waiter(connection)


# Для клиентов
@order_websocket_router.websocket("/orders/ws/client/{order_id}")
async def client_order_websocket(
        websocket: WebSocket,
        order_id: int,
        access_token: str = None  # или код доступа к заказу
):
    # Валидируем доступ клиента к заказу
    # Можно использовать access_token или код из SMS

    connection = await order_manager.connect_client(websocket, order_id)

    try:
        # Отправляем текущий статус при подключении
        async with AsyncSessionLocal() as session:
            order = await session.get(OrderDB, order_id)
            if order:
                await websocket.send_json({
                    "type": "initial_status",
                    "order_id": order_id,
                    "status": order.status,
                    "items": order.items  # или детали заказа
                })

        # Клиент только слушает, не отправляет команды
        while True:
            # Можно добавить heartbeat/ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await order_manager.disconnect_client(websocket, order_id)
