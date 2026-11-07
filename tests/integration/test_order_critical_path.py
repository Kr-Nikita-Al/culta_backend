"""HTTP + WebSocket + real auth/DAL/transactions on a migrated PostgreSQL."""
import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from starlette.websockets import WebSocketDisconnect

from db import OrderDB, OrderProductAssociationDB, STATUS_TYPE, UserRoleDB
from order.actions.update_order_action import __update_order_by_id

pytestmark = pytest.mark.integration


def create(pg, role='admin_a', items=None, company='company_a', client='client_a'):
    if items is None:
        items = [{'product_card_id': str(pg.ids['product_a']), 'quantity': 2},
                 {'product_card_id': str(pg.ids['product_a2']), 'quantity': 3}]
    return pg.client.post('/order/create', headers=pg.headers(role), json={
        'company_id': str(pg.ids[company]), 'user_id': str(pg.ids[client]),
        'comment': 'staff-only test note', 'order_items': items,
    })


def read(pg, oid, role='admin_a', company='company_a'):
    params = {'order_id': oid}
    if company:
        params['company_id'] = str(pg.ids[company])
    return pg.client.get('/order/get_by_id', headers=pg.headers(role), params=params)


def status(pg, oid, value, role='admin_a'):
    return pg.client.patch('/order/update_status_by_id', headers=pg.headers(role),
                           params={'order_id': oid, 'new_status': value})


def counts(pg):
    with pg.engine.connect() as conn:
        return tuple(conn.execute(select(func.count()).select_from(model)).scalar_one()
                     for model in (OrderDB, OrderProductAssociationDB))


def test_create_commit_and_public_response(pg):
    response = create(pg)
    assert response.status_code == 200, response.text
    oid = response.json()['order_id']
    assert response.json()['price'] == '798.75'
    # A new DB connection must see a committed order and both positions.
    assert counts(pg) == (1, 2)
    staff = read(pg, oid).json()
    assert staff['price'] == '798.75' and len(staff['order_items']) == 2
    assert staff['comment'] == 'staff-only test note'
    public = read(pg, oid, 'client_a', None)
    assert public.status_code == 200
    assert 'comment' not in public.json()
    assert 'cost_price' not in public.text


def test_fractional_total_is_exact_in_rest_and_websocket(pg):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=0.10 WHERE product_card_id=:id'), {'id': pg.ids['product_a']})
        connection.execute(text('UPDATE product_card SET price=0.20 WHERE product_card_id=:id'), {'id': pg.ids['product_a2']})
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as staff:
        ws_login(pg, staff, 'admin_a')
        assert staff.receive_json()['type'] == 'ready'
        response = create(pg, items=[{'product_card_id': str(pg.ids['product_a']), 'quantity': 3},
                                    {'product_card_id': str(pg.ids['product_a2']), 'quantity': 2}])
        assert response.status_code == 200, response.text
        assert response.json()['price'] == '0.70'
        assert staff.receive_json()['order']['price'] == '0.70'
        public = read(pg, response.json()['order_id'], 'client_a', None).json()
        assert public['price'] == '0.70'
        assert {item['product_info']['price'] for item in public['order_items']} == {'0.10', '0.20'}


def test_total_overflow_rolls_back_order(pg):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=9999999999999999.99'))
    response = create(pg)
    assert response.status_code == 422, response.text
    assert counts(pg) == (0, 0)


@pytest.mark.parametrize('bad', ['missing', 'foreign', 'inactive', 'unknown_activity', 'duplicate'])
def test_failed_second_position_leaves_no_order_or_positions(pg, bad):
    if bad == 'unknown_activity':
        with pg.engine.begin() as connection:
            connection.execute(text('UPDATE product_card SET is_active=NULL WHERE product_card_id=:id'), {'id': pg.ids['inactive']})
    products = {'missing': uuid4(), 'foreign': pg.ids['product_b'],
                'inactive': pg.ids['inactive'], 'unknown_activity': pg.ids['inactive'], 'duplicate': pg.ids['product_a']}
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as staff:
        ws_login(pg, staff, 'admin_a')
        assert staff.receive_json()['type'] == 'ready'
        response = create(pg, items=[{'product_card_id': str(pg.ids['product_a']), 'quantity': 1},
                                     {'product_card_id': str(products[bad]), 'quantity': 1}])
        assert response.status_code == (409 if bad == 'duplicate' else 422), response.text
        assert counts(pg) == (0, 0)
        staff.send_json({'type': 'unsupported'})
        assert staff.receive_json()['type'] == 'error'  # no new_order for rolled-back writes


@pytest.mark.parametrize('quantity', [0, -1, 1.5, True, '2', 2147483648])
def test_invalid_creation_quantity_has_no_writes_or_events(pg, quantity):
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as staff:
        ws_login(pg, staff, 'admin_a')
        assert staff.receive_json()['type'] == 'ready'
        response = create(pg, items=[{'product_card_id': str(pg.ids['product_a']), 'quantity': 1},
                                    {'product_card_id': str(pg.ids['product_a2']), 'quantity': quantity}])
        assert response.status_code == 422, response.text
        assert counts(pg) == (0, 0)
        staff.send_json({'type': 'unsupported'})
        assert staff.receive_json()['type'] == 'error'


def test_real_authentication_and_company_access(pg):
    assert pg.client.get('/order/get_all').status_code == 401
    assert pg.client.get('/order/get_all', headers={'Authorization': 'Bearer invalid'}).status_code == 401
    assert create(pg, role='client_a').status_code == 403
    assert create(pg, role='admin_b').status_code == 403
    oid = create(pg).json()['order_id']
    assert read(pg, oid, 'admin_b').status_code == 403
    assert read(pg, oid, 'admin_b', 'company_b').status_code == 403
    assert read(pg, oid, 'client_b', None).status_code == 403
    assert status(pg, oid, 'processing', 'admin_b').status_code == 403
    assert pg.client.patch('/order/update_by_id', headers=pg.headers('admin_b'),
                           params={'order_id': oid}, json={'comment': 'forbidden'}).status_code == 403
    own_list = pg.client.get('/order/get_all', headers=pg.headers('admin_b'),
                             params={'company_id': str(pg.ids['company_b'])})
    assert own_list.status_code == 200 and own_list.json()['orders'] == []
    other_client = pg.client.get('/order/get_all', headers=pg.headers('client_b'))
    assert other_client.status_code == 200 and other_client.json()['orders'] == []
    assert read(pg, oid).json()['status'] == 'created'


def test_legacy_status_permissions_and_terminal_state(pg):
    oid = create(pg).json()['order_id']
    # Historical orders have no check and keep their previous closing workflow.
    with pg.engine.begin() as conn:
        conn.execute(update(OrderDB).where(OrderDB.order_id == UUID(oid)).values(check_id=None))
    assert status(pg, oid, 'processing', 'waiter_a').status_code == 422
    assert status(pg, oid, 'processing', 'cook_a').status_code == 200
    assert status(pg, oid, 'closed', 'cook_a').status_code == 422
    assert status(pg, oid, 'completed', 'cook_a').status_code == 200
    assert status(pg, oid, 'closed', 'waiter_a').status_code == 200
    assert status(pg, oid, 'processing').status_code == 409
    assert pg.client.patch('/order/update_by_id', headers=pg.headers(),
        params={'order_id': oid}, json={'comment': 'late edit'}).status_code == 409
    assert read(pg, oid).json()['status'] == 'closed'


def test_patch_rolls_back_first_position_when_second_is_missing(pg):
    oid = create(pg).json()['order_id']
    response = pg.client.patch('/order/update_by_id', headers=pg.headers(),
        params={'order_id': oid}, json={'comment': 'must roll back', 'order_items': [
            {'product_card_id': str(pg.ids['product_a']), 'quantity': 9},
            {'product_card_id': str(uuid4()), 'quantity': 1}]})
    assert response.status_code == 404, response.text
    saved = read(pg, oid).json()
    assert saved['comment'] == 'staff-only test note'
    assert {x['product_card_id']: x['quantity'] for x in saved['order_items']}[str(pg.ids['product_a'])] == 2


def ws_login(pg, socket, role):
    socket.send_json({'type': 'authenticate', 'token': pg.token(role)})


def test_websocket_events_are_company_scoped_with_real_roles(pg):
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as a:
        ws_login(pg, a, 'admin_a')
        assert a.receive_json()['type'] == 'ready'
        with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_b"]}') as b:
            ws_login(pg, b, 'admin_b')
            assert b.receive_json()['type'] == 'ready'
            response = create(pg)
            assert response.status_code == 200
            oid = response.json()['order_id']
            event = a.receive_json()
            assert event['type'] == 'new_order' and event['order']['order_id'] == oid
            b.send_json({'type': 'unsupported'})
            assert b.receive_json()['type'] == 'error'  # no foreign event queued
            with pg.client.websocket_connect(f'/ws/orders/ws/client/{oid}') as client:
                ws_login(pg, client, 'client_a')
                assert client.receive_json()['type'] == 'initial_status'
                assert status(pg, oid, 'processing').status_code == 200
                assert a.receive_json()['order']['status'] == 'processing'
                public_event = client.receive_json()
                assert public_event['status'] == 'processing'
                assert 'comment' not in public_event['order']
                b.send_json({'type': 'unsupported'})
                assert b.receive_json()['type'] == 'error'


def test_websocket_rejects_foreign_roles_and_rechecks_revocation(pg):
    path = f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}'
    with pg.client.websocket_connect(path) as foreign:
        ws_login(pg, foreign, 'admin_b')
        with pytest.raises(WebSocketDisconnect) as error:
            foreign.receive_json()
        assert error.value.code == 1008
    with pg.client.websocket_connect(path) as own:
        ws_login(pg, own, 'admin_a')
        assert own.receive_json()['type'] == 'ready'
        with pg.engine.begin() as conn:
            conn.execute(update(UserRoleDB).where(UserRoleDB.user_id == pg.ids['admin_a']).values(is_active=False))
        own.send_json({'type': 'unsupported'})
        with pytest.raises(WebSocketDisconnect) as error:
            own.receive_json()
        assert error.value.code == 1008


def test_client_socket_rejects_foreign_order_and_closes_on_completion(pg):
    oid = create(pg).json()['order_id']
    path = f'/ws/orders/ws/client/{oid}'
    with pg.client.websocket_connect(path) as foreign:
        ws_login(pg, foreign, 'client_b')
        with pytest.raises(WebSocketDisconnect) as error:
            foreign.receive_json()
        assert error.value.code == 1008
    with pg.client.websocket_connect(path) as own:
        ws_login(pg, own, 'client_a')
        assert own.receive_json()['type'] == 'initial_status'
        assert status(pg, oid, 'processing').status_code == 200
        assert own.receive_json()['status'] == 'processing'
        assert status(pg, oid, 'completed').status_code == 200
        assert own.receive_json()['type'] == 'status_changed'
        assert own.receive_json()['type'] == 'order_finished'
        with pytest.raises(WebSocketDisconnect) as error:
            own.receive_json()
        assert error.value.code == 1000


def test_concurrent_edit_waits_for_lock_and_rechecks_closed_status(pg):
    oid = UUID(create(pg).json()['order_id'])

    async def scenario():
        async with pg.sessions() as locker:
            async with locker.begin():
                await locker.execute(select(OrderDB.order_id).where(OrderDB.order_id == oid).with_for_update())

                async def edit():
                    async with pg.sessions() as contender:
                        return await __update_order_by_id({'comment': 'must not be written'}, oid, contender,
                                                          expected_status=STATUS_TYPE.CREATED)

                task = asyncio.create_task(edit())
                try:
                    async def wait_for_database_lock():
                        async with pg.async_engine.connect() as observer:
                            while True:
                                waiting = (await observer.execute(text(
                                    "SELECT count(*) FROM pg_stat_activity WHERE application_name=:name "
                                    "AND wait_event_type='Lock'"), {'name': pg.schema})).scalar_one()
                                if waiting:
                                    return
                                await asyncio.sleep(0.01)
                    await asyncio.wait_for(wait_for_database_lock(), timeout=5)
                    assert not task.done()
                    await locker.execute(update(OrderDB).where(OrderDB.order_id == oid).values(status=STATUS_TYPE.CLOSED))
                except BaseException:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise
            with pytest.raises(HTTPException) as error:
                await asyncio.wait_for(task, timeout=5)
            assert error.value.status_code == 409

    asyncio.run(scenario())
    saved = read(pg, str(oid)).json()
    assert saved['status'] == 'closed' and saved['comment'] == 'staff-only test note'
