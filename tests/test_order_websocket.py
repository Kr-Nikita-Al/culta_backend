import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from threading import Event
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from db import STATUS_TYPE
from order.interface_response import GetClientOrderResponse, GetStaffOrderResponse
from order.websocket import api_handlers as ws_api
from order.websocket.manager import ConnectionManager
from order import api_handlers as rest
from product_card.interface_response import GetClientProductCardResponse
from utils.money import MoneyResponse, PercentageResponse
from auth.model_dal import create_access_token
from jose import jwt
import settings
import time

REAL_STATUS_UPDATE = rest.update_status_by_id


@pytest.fixture
def context(monkeypatch):
    # Database-backed section gate is exercised by PostgreSQL integration tests.
    monkeypatch.setattr(ws_api, 'check_order_module', AsyncMock())
    uid, cid, oid = uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    order = GetStaffOrderResponse(order_id=oid, company_id=cid, user_id=uid,
        staff_id=uid, creator_id=uid, updater_id=uid, time_created=now,
        time_updated=now, status=STATUS_TYPE.CREATED, cocking_time=0,
        comment='Staff only', price=0, bonus_transaction=0, order_items=[])
    manager = ConnectionManager()
    disconnected = Event()
    original_client_disconnect = manager.disconnect_client
    original_staff_disconnect = manager.disconnect_waiter

    async def disconnect_client(*args):
        await original_client_disconnect(*args)
        disconnected.set()

    async def disconnect_staff(*args):
        await original_staff_disconnect(*args)
        disconnected.set()

    monkeypatch.setattr(manager, 'disconnect_client', disconnect_client)
    monkeypatch.setattr(manager, 'disconnect_waiter', disconnect_staff)
    sessions = []

    @asynccontextmanager
    async def session():
        sessions.append('opened')
        try:
            yield object()
        finally:
            sessions.append('closed')

    async def get_order(order_id, staff, db):
        assert order_id == oid
        return order if staff else GetClientOrderResponse.parse_obj(order.dict())

    user = SimpleNamespace(user_id=uid, is_active=True)
    auth = AsyncMock(return_value=user)
    role = SimpleNamespace(is_admin=True, is_owner=False, is_waiter=False, is_cook=False)
    monkeypatch.setattr(ws_api, 'async_session', session)
    monkeypatch.setattr(ws_api, '__get_user_from_token', auth)
    monkeypatch.setattr(ws_api, '__get_user_role_model', AsyncMock(return_value=role))
    monkeypatch.setattr(ws_api, '__get_order_by_id', get_order)
    monkeypatch.setattr(ws_api, 'order_manager', manager)
    update = AsyncMock()
    monkeypatch.setattr(rest, 'update_status_by_id', update)
    app = FastAPI()
    app.include_router(ws_api.order_websocket_router)

    @app.post('/test-only/emit')
    async def emit_event():
        await manager.notify_order_update(oid, {'type': 'order_updated', 'order': jsonable_encoder(order)})
        return {'ok': True}

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, order=order, manager=manager,
            user=user, auth=auth, role=role, update=update, sessions=sessions, disconnected=disconnected)


def login(socket):
    socket.send_json({'type': 'authenticate', 'token': create_access_token({'sub': 'test@example.com'})})


def test_client_uuid_initial_snapshot_and_cleanup(context):
    with context.client.websocket_connect(f'/orders/ws/client/{context.order.order_id}') as socket:
        login(socket)
        message = socket.receive_json()
        assert message['order_id'] == str(context.order.order_id)
        assert message['status'] == 'created'
        assert message['order_items'] == []
        assert 'comment' not in message
        assert context.sessions == ['opened', 'closed'] * 2
        socket.send_text('ping')
        assert socket.receive_text() == 'pong'
    assert context.disconnected.wait(2)
    assert not context.manager.order_connections


@pytest.mark.parametrize('status', [STATUS_TYPE.COMPLETED, STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED])
def test_finished_client_receives_snapshot_then_close(context, status):
    context.order.status = status
    with context.client.websocket_connect(f'/orders/ws/client/{context.order.order_id}') as socket:
        login(socket)
        assert socket.receive_json()['type'] == 'initial_status'
        assert socket.receive_json()['status'] == status.value
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1000
    assert not context.manager.order_connections


@pytest.mark.parametrize('reason', ['token', 'owner', 'inactive', 'missing_auth'])
def test_client_access_rejected(context, reason):
    if reason == 'token':
        context.auth.side_effect = HTTPException(401)
    elif reason == 'owner':
        context.user.user_id = uuid4()
    elif reason == 'inactive':
        context.user.is_active = False
    with context.client.websocket_connect(f'/orders/ws/client/{context.order.order_id}') as socket:
        if reason == 'missing_auth':
            socket.send_json({})
        else:
            login(socket)
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008
    assert not context.manager.order_connections


def test_staff_validation_and_rest_reuse(context):
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={context.order.company_id}') as socket:
        login(socket)
        assert socket.receive_json()['type'] == 'ready'
        for command in [[], {'type': 'update_status', 'order_id': 'bad', 'status': 'created'},
                        {'type': 'update_status', 'order_id': str(context.order.order_id), 'status': 'cancelled'}]:
            socket.send_json(command)
            assert socket.receive_json()['status'] == 422
        context.update.side_effect = HTTPException(409, 'Order changed')
        socket.send_json({'type': 'update_status', 'order_id': str(context.order.order_id), 'status': 'processing'})
        assert socket.receive_json()['status'] == 409
        args = context.update.call_args.args
        assert args[0] == context.order.order_id
        assert args[1] == STATUS_TYPE.PROCESSING
    assert context.disconnected.wait(2)
    assert not context.manager.company_connections


def test_staff_cannot_update_other_company(context):
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={uuid4()}') as socket:
        login(socket)
        socket.receive_json()
        socket.send_json({'type': 'update_status', 'order_id': str(context.order.order_id), 'status': 'processing'})
        assert socket.receive_json()['status'] == 403
    context.update.assert_not_called()


def test_staff_requires_role(context):
    context.role.is_admin = False
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={context.order.company_id}') as socket:
        login(socket)
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


def test_manager_isolates_company_filters_client_and_cleans_failures(context):
    async def run():
        manager = ConnectionManager()
        staff, other, client, broken = [AsyncMock() for _ in range(4)]
        manager.register_waiter(staff, context.order.company_id)
        manager.register_waiter(other, uuid4())
        manager.register_waiter(broken, context.order.company_id)
        broken.send_json.side_effect = RuntimeError('Disconnected')
        manager.register_client(client, str(context.order.order_id))
        context.order.status = STATUS_TYPE.CANCELED
        payload_order = jsonable_encoder(context.order)
        sample_values = {str: '', int: 0, float: 0.0, bool: False, UUID: str(uuid4()),
                         MoneyResponse: '0.00', PercentageResponse: '0.00'}
        product = {name: sample_values[field.type_] for name, field in GetClientProductCardResponse.__fields__.items()}
        product['cost_price'] = 123.45
        product['product_release_type'] = 'staff-only'
        product.update(creator_id=str(uuid4()), updater_id=str(uuid4()),
                       time_created='2026-01-01T00:00:00Z', time_updated='2026-01-01T00:00:00Z')
        payload_order['order_items'] = [{'id': str(uuid4()), 'order_id': str(context.order.order_id),
            'product_card_id': product['product_card_id'], 'quantity': 2, 'product_info': product}]
        await manager.notify_order_update(context.order.order_id,
            {'type': 'order_updated', 'order': payload_order})
        staff.send_json.assert_awaited_once()
        assert 'cost_price' not in str(staff.send_json.call_args.args[0])
        other.send_json.assert_not_called()
        payload = client.send_json.call_args_list[0].args[0]
        assert 'comment' not in payload['order']
        assert 'cost_price' not in payload['order']['order_items'][0]['product_info']
        assert 'product_release_type' not in payload['order']['order_items'][0]['product_info']
        assert payload['status'] == 'canceled'
        client.close.assert_awaited_once_with(code=1000)
        assert not manager.order_connections
        assert broken not in manager.company_connections[context.order.company_id]
    asyncio.run(run())


@pytest.mark.parametrize('event_type', ['new_order', 'order_updated'])
def test_manager_rejects_foreign_company_payload(context, event_type):
    async def run():
        manager = ConnectionManager()
        staff = AsyncMock()
        wrong_company = uuid4()
        manager.register_waiter(staff, wrong_company)
        with pytest.raises(ValueError, match='company'):
            await manager.broadcast_to_company(wrong_company, {
                'type': event_type, 'order': jsonable_encoder(context.order),
            })
        staff.send_json.assert_not_awaited()
    asyncio.run(run())


def test_manager_rejects_wrong_order_before_any_delivery(context):
    async def run():
        manager = ConnectionManager()
        staff, client = AsyncMock(), AsyncMock()
        wrong_order = uuid4()
        manager.register_waiter(staff, context.order.company_id)
        manager.register_client(client, wrong_order)
        with pytest.raises(ValueError, match='Order'):
            await manager.notify_order_update(wrong_order, {
                'type': 'order_updated', 'order': jsonable_encoder(context.order),
            })
        staff.send_json.assert_not_awaited()
        client.send_json.assert_not_awaited()
    asyncio.run(run())


def test_staff_role_in_one_company_cannot_subscribe_to_another(context, monkeypatch):
    async def role_for_company(user_id, session, company_id):
        return SimpleNamespace(is_admin=company_id == context.order.company_id,
                               is_owner=False, is_waiter=False, is_cook=False)
    monkeypatch.setattr(ws_api, '__get_user_role_model', role_for_company)
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={uuid4()}') as socket:
        login(socket)
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008
    assert not context.manager.company_connections


@pytest.mark.parametrize('event_type', ['new_order', 'order_updated'])
def test_two_company_sockets_receive_only_their_rest_notifications(context, monkeypatch, event_type):
    # One employee can have roles in both companies, but each tab has one scope.
    company_a = context.order.company_id
    company_b = uuid4()
    order_a = context.order
    order_b = order_a.copy(update={'order_id': uuid4(), 'company_id': company_b})
    orders = {order.order_id: order for order in (order_a, order_b)}
    monkeypatch.setattr(rest, 'order_manager', context.manager)

    async def get_order(order_id, is_staff, session):
        return orders[order_id]
    monkeypatch.setattr(rest, '__get_order_by_id', get_order)

    async def emit():
        # Exercise the actual REST notification functions on the ASGI event loop.
        for order in (order_a, order_b):
            if event_type == 'new_order':
                await rest._notify_new_order(order)
            else:
                await rest._notify_order_updated(order.order_id, object())

    with context.client.websocket_connect(f'/orders/ws/staff?company_id={company_a}') as socket_a:
        login(socket_a)
        assert socket_a.receive_json()['type'] == 'ready'
        with context.client.websocket_connect(f'/orders/ws/staff?company_id={company_b}') as socket_b:
            login(socket_b)
            assert socket_b.receive_json()['type'] == 'ready'
            context.client.portal.call(emit)
            for socket, expected in ((socket_a, order_a), (socket_b, order_b)):
                event = socket.receive_json()
                assert event['type'] == event_type
                assert event['order']['order_id'] == str(expected.order_id)
                assert event['order']['company_id'] == str(expected.company_id)
                # A response barrier catches any extra cross-company event
                # already queued, without sleeps or hanging negative receives.
                socket.send_json({'type': 'unsupported'})
                assert socket.receive_json()['type'] == 'error'
        socket_a.send_json({'type': 'unsupported'})
        assert socket_a.receive_json()['type'] == 'error'


def test_missing_order_returns_error_without_update(context, monkeypatch):
    monkeypatch.setattr(ws_api, '__get_order_by_id', AsyncMock(return_value=None))
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={context.order.company_id}') as socket:
        login(socket)
        socket.receive_json()
        socket.send_json({'type': 'update_status', 'order_id': str(context.order.order_id), 'status': 'processing'})
        assert socket.receive_json()['status'] == 404
    context.update.assert_not_called()


def test_database_error_closes_and_cleans_socket(context, monkeypatch):
    monkeypatch.setattr(ws_api, '__get_order_by_id', AsyncMock(side_effect=RuntimeError('test DB failure')))
    with context.client.websocket_connect(f'/orders/ws/client/{context.order.order_id}') as socket:
        login(socket)
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1011
    assert context.disconnected.wait(2)
    assert not context.manager.order_connections


@pytest.mark.parametrize('claims,key,algorithm', [
    ({'sub': 'test@example.com', 'exp': 1}, None, 'HS256'),
    ({'sub': 'test@example.com'}, None, 'HS256'),
    ({'exp': 9999999999}, None, 'HS256'),
    ({'sub': '', 'exp': 9999999999}, None, 'HS256'),
    ({'sub': 'test@example.com', 'exp': 'tomorrow'}, None, 'HS256'),
    ({'sub': 'test@example.com', 'exp': 9999999999}, 'wrong-key', 'HS256'),
    ({'sub': 'test@example.com', 'exp': 9999999999}, None, 'HS384'),
])
def test_real_jwt_validation_before_db(context, claims, key, algorithm):
    token = jwt.encode(claims, key or settings.SECRET_KEY, algorithm=algorithm)
    with context.client.websocket_connect(f'/orders/ws/client/{context.order.order_id}') as socket:
        socket.send_json({'type': 'authenticate', 'token': token})
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008
    context.auth.assert_not_called()


@pytest.mark.parametrize('kind', ['client', 'staff'])
@pytest.mark.parametrize('revocation', ['inactive', 'access', 'expired'])
def test_open_socket_rechecks_on_input(context, monkeypatch, kind, revocation):
    path = f'client/{context.order.order_id}' if kind == 'client' else f'staff?company_id={context.order.company_id}'
    with context.client.websocket_connect('/orders/ws/' + path) as socket:
        login(socket)
        socket.receive_json()
        if revocation == 'inactive':
            context.user.is_active = False
        elif revocation == 'expired':
            monkeypatch.setattr(ws_api, 'token_expiry', lambda token: (_ for _ in ()).throw(HTTPException(401)))
        elif kind == 'staff':
            context.role.is_admin = False
        else:
            context.order.user_id = uuid4()
        if kind == 'client':
            socket.send_text('ping')
        else:
            socket.send_json({'type': 'update_status', 'order_id': str(context.order.order_id), 'status': 'processing'})
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008
    context.update.assert_not_called()
    assert context.disconnected.wait(2)
    assert not context.manager._authorizers


def test_idle_socket_rechecks_revoked_role(context, monkeypatch):
    monkeypatch.setattr(ws_api, 'ACCESS_RECHECK_SECONDS', 0.02)
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={context.order.company_id}') as socket:
        login(socket)
        socket.receive_json()
        context.role.is_admin = False
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


def test_idle_socket_expires_without_input(context):
    token = jwt.encode({'sub': 'test@example.com', 'exp': time.time() + 1.2}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    with context.client.websocket_connect(f'/orders/ws/client/{context.order.order_id}') as socket:
        socket.send_json({'type': 'authenticate', 'token': token})
        assert socket.receive_json()['type'] == 'initial_status'
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


@pytest.mark.parametrize('kind', ['staff', 'client'])
def test_event_after_access_revocation_is_not_delivered(context, kind):
    path = f'client/{context.order.order_id}' if kind == 'client' else f'staff?company_id={context.order.company_id}'
    with context.client.websocket_connect('/orders/ws/' + path) as socket:
        login(socket)
        socket.receive_json()
        if kind == 'staff':
            context.role.is_admin = False
        else:
            context.order.user_id = uuid4()
        assert context.client.post('/test-only/emit').status_code == 200
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


def test_command_cannot_override_user_or_company(context):
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={context.order.company_id}') as socket:
        login(socket)
        socket.receive_json()
        socket.send_json({'type': 'update_status', 'order_id': str(context.order.order_id),
                          'status': 'processing', 'user_id': str(uuid4()), 'company_id': str(uuid4())})
        assert socket.receive_json()['status'] == 422
    context.update.assert_not_called()


@pytest.mark.parametrize('failure,code', [(HTTPException(403), 1008), (RuntimeError('DB unavailable'), 1011)])
def test_manager_does_not_send_when_authorization_fails(failure, code):
    async def run():
        manager = ConnectionManager()
        ws = AsyncMock()
        company_id = uuid4()
        manager.register_waiter(ws, company_id, authorize=AsyncMock(side_effect=failure))
        await manager.broadcast_to_company(company_id, {'type': 'order_updated'})
        ws.send_json.assert_not_called()
        ws.close.assert_awaited_once_with(code=code)
        assert not manager.company_connections
        assert not manager._authorizers
    asyncio.run(run())


@pytest.mark.parametrize('role,old,new,expected', [
    ('waiter', 'created', 'processing', 422),
    ('cook', 'created', 'closed', 422),
    ('admin', 'created', 'completed', 200),
    ('waiter', 'created', 'completed', 200),
    ('admin', 'completed', 'processing', 422),
    ('owner', 'closed', 'processing', 409),
    ('admin', 'canceled', 'processing', 409),
    ('cook', 'created', 'processing', 200),
    ('cook', 'processing', 'completed', 200),
    ('waiter', 'completed', 'closed', 200),
    ('owner', 'created', 'canceled', 200),
])
def test_websocket_uses_real_rest_status_permissions(context, monkeypatch, role, old, new, expected):
    for name in ('admin', 'owner', 'waiter', 'cook'):
        setattr(context.role, 'is_' + name, name == role)
    context.order.status = STATUS_TYPE(old)
    monkeypatch.setattr(rest, 'update_status_by_id', REAL_STATUS_UPDATE)
    monkeypatch.setattr(rest, '__get_order_by_id', AsyncMock(return_value=context.order))
    monkeypatch.setattr(rest, '__get_user_role_model', AsyncMock(return_value=context.role))
    update = AsyncMock(return_value=context.order.order_id)
    monkeypatch.setattr(rest, '__update_order_by_id', update)
    async def notified(*args):
        await context.manager.broadcast_to_company(context.order.company_id, {'type': 'order_updated'})
    monkeypatch.setattr(rest, '_notify_order_updated', notified)
    with context.client.websocket_connect(f'/orders/ws/staff?company_id={context.order.company_id}') as socket:
        login(socket)
        socket.receive_json()
        socket.send_json({'type': 'update_status', 'order_id': str(context.order.order_id), 'status': new})
        response = socket.receive_json()
        if expected == 200:
            assert response['type'] == 'order_updated'
            assert update.call_args.kwargs['expected_status'] == STATUS_TYPE(old)
        else:
            assert response['status'] == expected
            update.assert_not_called()
