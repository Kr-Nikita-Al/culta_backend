"""HTTP regressions with database actions and authentication replaced by fakes."""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, DataError, IntegrityError, InterfaceError, OperationalError

from order import api_handlers as api
from db import STATUS_TYPE
from order.actions import get_orders_action
from order.interface_response import CreateOrderResponse, GetStaffOrderResponse


@pytest.fixture
def context(monkeypatch):
    user_id, company_id, order_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    order = GetStaffOrderResponse(
        order_id=order_id, company_id=company_id, user_id=user_id,
        staff_id=user_id, creator_id=user_id, updater_id=user_id,
        time_created=now, time_updated=now, status=STATUS_TYPE.CREATED,
        cocking_time=0, comment='', price=0, bonus_transaction=0, order_items=[],
    )
    role = SimpleNamespace(is_admin=True, is_owner=False, is_waiter=False, is_cook=False)
    db = object()

    async def fake_db():
        yield db

    async def fake_user():
        return SimpleNamespace(user_id=user_id)

    app = FastAPI()
    app.include_router(api.order_router, prefix='/order')
    # This suite mocks the database boundary; real section gates are tested in PostgreSQL.
    for dependency in api.order_router.dependencies:
        app.dependency_overrides[dependency.dependency] = lambda: None
    app.dependency_overrides[api.get_db] = fake_db
    app.dependency_overrides[api.__get_user_from_token] = fake_user

    get_order = AsyncMock(return_value=order)
    update = AsyncMock(return_value=order_id)
    create = AsyncMock(return_value=CreateOrderResponse(**order.dict()))
    monkeypatch.setattr(api, '__get_order_by_id', get_order)
    monkeypatch.setattr(api, '__get_company_by_id', AsyncMock(return_value=SimpleNamespace(company_id=company_id)))
    monkeypatch.setattr(api, '__get_user_role_model', AsyncMock(return_value=role))
    monkeypatch.setattr(api, '__get_user_by_id', AsyncMock(return_value=SimpleNamespace(user_id=user_id)))
    monkeypatch.setattr(api, '__update_order_by_id', update)
    monkeypatch.setattr(api, '__create_order', create)
    notify = AsyncMock()
    monkeypatch.setattr(api.order_manager, 'notify_order_update', notify, raising=False)
    broadcast = AsyncMock()
    monkeypatch.setattr(api.order_manager, 'broadcast_to_company', broadcast, raising=False)

    with TestClient(app) as client:
        yield SimpleNamespace(client=client, app=app, order=order, role=role,
                              get_order=get_order, update=update, create=create,
                              notify=notify, broadcast=broadcast, db=db)


def patch_order(ctx, body):
    return ctx.client.patch('/order/update_by_id', params={'order_id': str(ctx.order.order_id)}, json=body)


def patch_status(ctx, new_status='processing'):
    return ctx.client.patch('/order/update_status_by_id',
                            params={'order_id': str(ctx.order.order_id), 'new_status': new_status})


@pytest.mark.parametrize('staff', [False, True])
def test_missing_order_is_404(context, staff):
    context.get_order.return_value = None
    params = {'order_id': str(context.order.order_id)}
    if staff:
        params['company_id'] = str(context.order.company_id)
    response = context.client.get('/order/get_by_id', params=params)
    assert response.status_code == 404


def test_staff_cannot_read_another_company_order(context):
    response = context.client.get('/order/get_by_id', params={
        'order_id': str(context.order.order_id), 'company_id': str(uuid4()),
    })
    assert response.status_code == 403


def test_client_cannot_read_another_users_order(context):
    context.order.user_id = uuid4()
    response = context.client.get('/order/get_by_id', params={'order_id': str(context.order.order_id)})
    assert response.status_code == 403


def test_staff_can_read_own_company_order(context):
    response = context.client.get('/order/get_by_id', params={
        'order_id': str(context.order.order_id), 'company_id': str(context.order.company_id),
    })
    assert response.status_code == 200
    assert response.json()['order_id'] == str(context.order.order_id)


@pytest.mark.parametrize('endpoint', ['details', 'status'])
def test_patch_missing_order_is_404(context, endpoint):
    context.get_order.return_value = None
    response = patch_order(context, {'comment': 'test'}) if endpoint == 'details' else patch_status(context)
    assert response.status_code == 404
    context.update.assert_not_awaited()
    context.notify.assert_not_awaited()


@pytest.mark.parametrize('status', [STATUS_TYPE.CLOSED, STATUS_TYPE.CANCELED])
@pytest.mark.parametrize('endpoint', ['details', 'status'])
def test_finalized_order_is_rejected_before_any_write(context, status, endpoint):
    context.order.status = status
    response = (patch_order(context, {'order_items': [{'product_card_id': str(uuid4()), 'quantity': 2}]})
                if endpoint == 'details' else patch_status(context))
    assert response.status_code == 409
    context.update.assert_not_awaited()
    context.notify.assert_not_awaited()


@pytest.mark.parametrize('endpoint', ['details', 'status'])
def test_unauthorized_edit_does_not_write(context, endpoint):
    context.role.is_admin = False
    response = patch_order(context, {'comment': 'test'}) if endpoint == 'details' else patch_status(context)
    assert response.status_code == 403
    context.update.assert_not_awaited()


def test_invalid_status_transition_does_not_write(context):
    assert patch_status(context, 'created').status_code == 422
    context.update.assert_not_awaited()


@pytest.mark.parametrize('body', [{}, {'order_items': []}, {'cocking_time': None}])
def test_empty_patch_is_422(context, body):
    assert patch_order(context, body).status_code == 422
    context.update.assert_not_awaited()


def test_empty_items_are_not_passed_as_a_database_column(context):
    response = patch_order(context, {'comment': 'updated', 'order_items': []})
    assert response.status_code == 200
    params = context.update.await_args.kwargs
    assert params['update_order_params'] == {'comment': 'updated', 'updater_id': context.order.user_id}
    assert params['expected_status'] == STATUS_TYPE.CREATED


def test_null_optional_time_does_not_raise_500(context):
    assert patch_order(context, {'comment': 'updated', 'cocking_time': None}).status_code == 200


@pytest.mark.parametrize('body', [
    {'status': 'closed'}, {'comment': 'changed', 'status': 'closed'},
    {'comment': 'x' * 501}, {'cocking_time': -1},
])
def test_invalid_fields_are_422_before_write(context, body):
    assert patch_order(context, body).status_code == 422
    context.update.assert_not_awaited()


@pytest.mark.parametrize('endpoint', ['details', 'status'])
def test_update_conflict_is_checked_before_reload_or_notification(context, endpoint):
    context.update.return_value = None
    response = patch_order(context, {'comment': 'test'}) if endpoint == 'details' else patch_status(context)
    assert response.status_code == 409
    assert context.get_order.await_count == 1
    context.notify.assert_not_awaited()


@pytest.mark.parametrize('endpoint', ['details', 'status'])
@pytest.mark.parametrize('failure', ['missing', 'send', 'reload'])
def test_committed_update_succeeds_when_notification_is_unavailable(context, monkeypatch, endpoint, failure):
    if failure == 'missing':
        monkeypatch.delattr(api.order_manager, 'notify_order_update')
    elif failure == 'send':
        context.notify.side_effect = RuntimeError('test notification failure')
    else:
        context.get_order.side_effect = [context.order, RuntimeError('test reload failure')]
    response = patch_order(context, {'comment': 'test'}) if endpoint == 'details' else patch_status(context)
    assert response.status_code == 200
    assert response.json() == {'updated_order_id': str(context.order.order_id)}


def test_notification_payload_is_json_serializable(context):
    assert patch_status(context).status_code == 200
    payload = context.notify.await_args.args[1]
    json.dumps(payload)
    assert payload['order']['order_id'] == str(context.order.order_id)


@pytest.mark.parametrize('error_type, expected', [
    (IntegrityError, 409), (DataError, 422), (OperationalError, 503),
    (InterfaceError, 503), (DBAPIError, 500),
])
@pytest.mark.parametrize('endpoint', ['get', 'create', 'patch'])
def test_database_errors_have_distinct_safe_responses(context, error_type, expected, endpoint):
    error = error_type('sensitive SQL', {}, RuntimeError('private driver details'))
    if endpoint == 'get':
        context.get_order.side_effect = error
        response = context.client.get('/order/get_by_id', params={'order_id': str(context.order.order_id)})
    elif endpoint == 'create':
        context.create.side_effect = error
        response = context.client.post('/order/create', json={
            'company_id': str(context.order.company_id), 'user_id': str(context.order.user_id),
        })
    else:
        context.update.side_effect = error
        response = patch_order(context, {'comment': 'test'})
    assert response.status_code == expected
    assert 'sensitive SQL' not in response.text
    assert 'private driver details' not in response.text


def test_create_survives_notification_failure_and_optional_null(context):
    context.broadcast.side_effect = RuntimeError('test send failure')
    response = context.client.post('/order/create', json={
        'company_id': str(context.order.company_id), 'user_id': str(context.order.user_id),
        'cocking_time': None,
    })
    assert response.status_code == 200
    assert response.json()['order_id'] == str(context.order.order_id)


def test_create_never_falls_back_to_cross_company_broadcast(context, monkeypatch):
    monkeypatch.delattr(api.order_manager, 'broadcast_to_company')
    global_broadcast = AsyncMock()
    monkeypatch.setattr(api.order_manager, 'broadcast_to_waiters', global_broadcast, raising=False)
    response = context.client.post('/order/create', json={
        'company_id': str(context.order.company_id), 'user_id': str(context.order.user_id),
    })
    assert response.status_code == 200
    global_broadcast.assert_not_awaited()


def test_new_order_notification_targets_its_company(context):
    response = context.client.post('/order/create', json={
        'company_id': str(context.order.company_id), 'user_id': str(context.order.user_id),
    })
    assert response.status_code == 200
    company_id, payload = context.broadcast.await_args.args
    assert company_id == context.order.company_id
    assert payload['order']['order_id'] == str(context.order.order_id)
    json.dumps(payload)


def test_failed_atomic_creation_does_not_emit_event(context):
    context.create.side_effect = IntegrityError('', {}, Exception())
    response = context.client.post('/order/create', json={
        'company_id': str(context.order.company_id), 'user_id': str(context.order.user_id),
        'order_items': [{'product_card_id': str(uuid4()), 'quantity': 2}],
    })
    assert response.status_code == 409
    context.broadcast.assert_not_awaited()


@pytest.mark.parametrize('quantity', [0, -1])
def test_create_rejects_non_positive_quantity(context, quantity):
    response = context.client.post('/order/create', json={
        'company_id': str(context.order.company_id), 'user_id': str(context.order.user_id),
        'order_items': [{'product_card_id': str(uuid4()), 'quantity': quantity}],
    })
    assert response.status_code == 422
    context.create.assert_not_awaited()


@pytest.mark.parametrize('staff', [True, False])
@pytest.mark.parametrize('orders', [None, []])
def test_empty_order_list_uses_concrete_response_type(monkeypatch, staff, orders):
    session = SimpleNamespace(begin=lambda: AsyncMock())
    dal = SimpleNamespace(get_orders_in_company=AsyncMock(return_value=orders),
                          get_user_orders=AsyncMock(return_value=orders))
    monkeypatch.setattr(get_orders_action, 'OrderDal', lambda _: dal)
    response = asyncio.run(get_orders_action.__get_orders(
        is_staff=staff, session=session, user_id=uuid4(), statuses=[], company_id=uuid4(),
    ))
    assert response.dict() == {'orders': []}
