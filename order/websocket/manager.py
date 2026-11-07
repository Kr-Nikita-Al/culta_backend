"""Process-local subscriptions; use a single worker until shared pub/sub exists."""
import asyncio
from collections import defaultdict
from uuid import UUID
from decimal import Decimal
from utils.money import encode_decimal

from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException
from order.interface_response import GetClientOrderResponse


class ConnectionManager:
    def __init__(self):
        self.company_connections = defaultdict(set)
        self.order_connections = defaultdict(set)
        self._locks = {}
        self._authorizers = {}

    def register_waiter(self, websocket, company_id, authorize=None):
        self.company_connections[UUID(str(company_id))].add(websocket)
        self._locks[websocket] = asyncio.Lock()
        self._authorizers[websocket] = authorize

    def register_client(self, websocket, order_id, authorize=None):
        self.order_connections[UUID(str(order_id))].add(websocket)
        self._locks[websocket] = asyncio.Lock()
        self._authorizers[websocket] = authorize

    async def connect_waiter(self, websocket, company_id):
        await websocket.accept()
        self.register_waiter(websocket, company_id)
        return websocket

    async def connect_client(self, websocket, order_id):
        await websocket.accept()
        self.register_client(websocket, order_id)
        return websocket

    async def disconnect_waiter(self, websocket):
        for key, connections in list(self.company_connections.items()):
            connections.discard(websocket)
            if not connections:
                self.company_connections.pop(key, None)
        self._locks.pop(websocket, None)
        self._authorizers.pop(websocket, None)

    async def disconnect_client(self, websocket, order_id):
        key = UUID(str(order_id))
        connections = self.order_connections.get(key)
        if connections is not None:
            connections.discard(websocket)
            if not connections:
                self.order_connections.pop(key, None)
        self._locks.pop(websocket, None)
        self._authorizers.pop(websocket, None)

    async def send(self, websocket, message):
        lock = self._locks.get(websocket)
        if lock is None:
            return False
        try:
            async with lock:
                authorize = self._authorizers.get(websocket)
                if authorize is not None:
                    try:
                        await asyncio.wait_for(authorize(), timeout=5)
                    except Exception as exc:
                        await asyncio.wait_for(websocket.close(code=1008 if isinstance(exc, HTTPException) else 1011), timeout=5)
                        return False
                await asyncio.wait_for(websocket.send_json(jsonable_encoder(message, custom_encoder={Decimal: encode_decimal})), timeout=5)
            return True
        except Exception:
            return False

    async def broadcast_to_company(self, company_id, message):
        company_id = UUID(str(company_id))
        # Fail closed if a caller accidentally routes an order to another tenant.
        if 'order' in message:
            if UUID(str(message['order']['company_id'])) != company_id:
                raise ValueError('Order company does not match the notification channel')
        connections = tuple(self.company_connections.get(company_id, ()))
        results = await asyncio.gather(*(self.send(ws, message) for ws in connections))
        for ws, sent in zip(connections, results):
            if not sent:
                await self.disconnect_waiter(ws)

    async def send_to_order(self, order_id, message):
        connections = tuple(self.order_connections.get(UUID(str(order_id)), ()))
        results = await asyncio.gather(*(self.send(ws, message) for ws in connections))
        for ws, sent in zip(connections, results):
            if not sent:
                await self.disconnect_client(ws, order_id)

    async def close_order(self, order_id):
        for ws in tuple(self.order_connections.get(UUID(str(order_id)), ())):
            try:
                await asyncio.wait_for(ws.close(code=1000), timeout=5)
            except Exception:
                pass
            finally:
                await self.disconnect_client(ws, order_id)

    async def notify_order_update(self, order_id, message):
        order = message['order']
        order_id = UUID(str(order_id))
        if UUID(str(order['order_id'])) != order_id:
            raise ValueError('Order does not match the notification channel')
        # Public DTO excludes staff comments and nested product cost prices.
        client_order = jsonable_encoder(GetClientOrderResponse.parse_obj(order))
        # Company channels are shared by staff with different financial permissions.
        from order.interface_response import GetStaffOrderResponse
        staff_order = jsonable_encoder(GetStaffOrderResponse.parse_obj(order))
        await self.broadcast_to_company(order['company_id'], {**message, 'order': staff_order})
        await self.send_to_order(order_id, {
            'type': 'status_changed', 'order_id': str(order_id),
            'status': client_order['status'], 'order': client_order,
        })
        if client_order['status'] in ('completed', 'closed', 'canceled'):
            await self.send_to_order(order_id, {
                'type': 'order_finished', 'order_id': str(order_id),
                'status': client_order['status'], 'message': 'Заказ завершен',
            })
            await self.close_order(order_id)


order_manager = ConnectionManager()
