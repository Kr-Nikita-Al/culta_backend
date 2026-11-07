"""Order sockets with short-lived sessions and REST-compatible status changes."""
import asyncio
import json
import logging
import math
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, constr
from typing import Optional
from jose import JWTError, jwt
from starlette.websockets import WebSocketState
import settings

from db import STATUS_TYPE
from db.session import async_session
from order.actions import __get_order_by_id
from order.websocket.manager import order_manager
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from company.modules import ensure_enabled

logger = logging.getLogger(__name__)
order_websocket_router = APIRouter()
ACCESS_RECHECK_SECONDS = 30


async def check_order_module(session, company_id):
    async with session.begin():
        await ensure_enabled(session, company_id, 'orders')


async def close_socket(websocket, code):
    if websocket.application_state == WebSocketState.CONNECTED:
        await websocket.close(code=code)


class StatusCommand(BaseModel):
    order_id: UUID
    status: STATUS_TYPE
    reason: Optional[constr(strip_whitespace=True, max_length=500)] = None

    class Config:
        extra = 'forbid'


def token_expiry(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                             options={'require_exp': True, 'require_sub': True})
        expires = payload['exp']
        if (not isinstance(payload['sub'], str) or not payload['sub'] or
                isinstance(expires, bool) or not isinstance(expires, (int, float)) or
                not math.isfinite(expires) or expires <= time.time()):
            raise ValueError('Invalid claims')
        return expires
    except (JWTError, ValueError, TypeError, OverflowError):
        raise HTTPException(401, 'Invalid access token') from None


async def current_socket_user(websocket, session):
    token_expiry(websocket.state.access_token)
    user = await __get_user_from_token(token=websocket.state.access_token, db=session)
    if user is None or not user.is_active:
        raise HTTPException(403, 'Forbidden')
    return user


async def receive_authorized(websocket, authorize):
    # No DB session remains open while waiting for network input. Idle sockets
    # expire at the token deadline and recheck revoked access at least every 30s.
    while True:
        remaining = token_expiry(websocket.state.access_token) - time.time()
        try:
            data = await asyncio.wait_for(websocket.receive_text(),
                                          timeout=min(ACCESS_RECHECK_SECONDS, max(0, remaining)))
        except asyncio.TimeoutError:
            await authorize()
            continue
        await authorize()
        return data


async def authenticate(websocket, session):
    # First-frame credentials keep bearer tokens out of URL/access logs.
    data = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    if not isinstance(data, dict) or data.get('type') != 'authenticate' or not isinstance(data.get('token'), str):
        raise HTTPException(401, 'Authentication required')
    websocket.state.access_token = data['token']
    return await current_socket_user(websocket, session)


@order_websocket_router.websocket('/orders/ws/staff')
async def waiter_orders_websocket(websocket: WebSocket, company_id: UUID):
    await websocket.accept()
    try:
        async with async_session() as session:
            user = await authenticate(websocket, session)
            role = await __get_user_role_model(user_id=user.user_id, session=session, company_id=company_id)
            await check_order_module(session, company_id)
            if not (role.is_admin or role.is_owner or role.is_waiter or role.is_cook):
                raise HTTPException(403, 'Forbidden')
        async def authorize():
            async with async_session() as session:
                current = await current_socket_user(websocket, session)
                if current.user_id != user.user_id:
                    raise HTTPException(403, 'Forbidden')
                role = await __get_user_role_model(user_id=current.user_id, session=session, company_id=company_id)
                await check_order_module(session, company_id)
                if not (role.is_admin or role.is_owner or role.is_waiter or role.is_cook):
                    raise HTTPException(403, 'Forbidden')

        order_manager.register_waiter(websocket, company_id, authorize=authorize)
        if not await order_manager.send(websocket, {'type': 'ready'}):
            return
        while True:
            raw = await receive_authorized(websocket, authorize)
            try:
                data = json.loads(raw)
                if not isinstance(data, dict) or data.get('type') != 'update_status':
                    raise ValueError('Unsupported command')
                command = StatusCommand.parse_obj({key: value for key, value in data.items() if key != 'type'})
                async with async_session() as session:
                    order = await __get_order_by_id(command.order_id, True, session)
                    if order is None:
                        raise HTTPException(404, 'Order not found')
                    if order.company_id != company_id:
                        raise HTTPException(403, 'Forbidden')
                    # Lazy import avoids router/manager import cycles.
                    from order.api_handlers import update_status_by_id
                    await update_status_by_id(command.order_id, command.status, session, user, reason=command.reason)
            except ValueError:
                await order_manager.send(websocket, {'type': 'error', 'status': 422, 'detail': 'Invalid command'})
            except HTTPException as exc:
                await order_manager.send(websocket, {'type': 'error', 'status': exc.status_code, 'detail': exc.detail})
    except WebSocketDisconnect:
        pass
    except (HTTPException, ValueError, TimeoutError):
        await close_socket(websocket, 1008)
    except Exception:
        logger.exception('Staff order socket failed')
        await close_socket(websocket, 1011)
    finally:
        await order_manager.disconnect_waiter(websocket)


@order_websocket_router.websocket('/orders/ws/client/{order_id}')
async def client_order_websocket(websocket: WebSocket, order_id: UUID):
    await websocket.accept()
    try:
        async with async_session() as session:
            user = await authenticate(websocket, session)
            order = await __get_order_by_id(order_id, False, session)
            if order is None or order.user_id != user.user_id:
                raise HTTPException(403, 'Forbidden')
            await check_order_module(session, order.company_id)
        async def authorize():
            async with async_session() as session:
                current = await current_socket_user(websocket, session)
                current_order = await __get_order_by_id(order_id, False, session)
                if (current.user_id != user.user_id or current_order is None or
                        current_order.user_id != current.user_id):
                    raise HTTPException(403, 'Forbidden')
                await check_order_module(session, current_order.company_id)

        order_manager.register_client(websocket, order_id, authorize=authorize)
        if not await order_manager.send(websocket, {'type': 'initial_status', **jsonable_encoder(order)}):
            return
        if order.status in (STATUS_TYPE.COMPLETED, STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED):
            await order_manager.send(websocket, {'type': 'order_finished', 'order_id': str(order_id), 'status': order.status})
            await order_manager.close_order(order_id)
            return
        while True:
            if await receive_authorized(websocket, authorize) == 'ping':
                await websocket.send_text('pong')
    except WebSocketDisconnect:
        pass
    except (HTTPException, ValueError, TimeoutError):
        await close_socket(websocket, 1008)
    except Exception:
        logger.exception('Client order socket failed')
        await close_socket(websocket, 1011)
    finally:
        await order_manager.disconnect_client(websocket, order_id)
