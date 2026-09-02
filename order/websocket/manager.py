from typing import Dict, Set
from collections import defaultdict


class ConnectionManager:
    def __init__(self):
        # Для официантов: все подключенные официанты
        self.active_waiters: Set = set()

        # Для клиентов: order_id -> set of connections
        self.order_connections: Dict[int, Set] = defaultdict(set)

        # Для админов/кухни: все подключенные админы
        self.active_admins: Set = set()

    async def connect_waiter(self, websocket):
        await websocket.accept()
        self.active_waiters.add(websocket)
        return websocket

    async def disconnect_waiter(self, websocket):
        self.active_waiters.discard(websocket)

    async def connect_client(self, websocket, order_id: int):
        await websocket.accept()
        self.order_connections[order_id].add(websocket)
        return websocket

    async def disconnect_client(self, websocket, order_id: int):
        if order_id in self.order_connections:
            self.order_connections[order_id].discard(websocket)
            if not self.order_connections[order_id]:
                del self.order_connections[order_id]

    async def connect_admin(self, websocket):
        await websocket.accept()
        self.active_admins.add(websocket)
        return websocket

    async def disconnect_admin(self, websocket):
        self.active_admins.discard(websocket)

    # Отправка сообщений разным группам
    async def broadcast_to_waiters(self, message: dict):
        disconnected = []
        for connection in self.active_waiters:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.active_waiters.discard(connection)

    async def send_to_order(self, order_id: int, message: dict):
        if order_id in self.order_connections:
            disconnected = []
            for connection in self.order_connections[order_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)

            for connection in disconnected:
                self.order_connections[order_id].discard(connection)

    async def broadcast_to_admins(self, message: dict):
        disconnected = []
        for connection in self.active_admins:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.active_admins.discard(connection)


order_manager = ConnectionManager()
