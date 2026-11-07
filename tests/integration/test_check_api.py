"""Service mode, exact payment and transaction boundaries on migrated PostgreSQL."""
import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update, func, text

from db import CheckDB, CompanyDB, OrderDB, OrderProductAssociationDB, STATUS_TYPE
from checks.service import close_check
from order.actions.update_order_action import __update_order_by_id
from tests.integration.test_order_critical_path import create, read, status, ws_login

pytestmark = pytest.mark.integration


def mode(pg, value='waiter_service'):
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).where(CompanyDB.company_id == pg.ids['company_a']).values(service_type=value))


def attach(pg, check, client='client_a', company='company_a'):
    return pg.client.post('/order/create', headers=pg.headers('admin_a'), json={
        'company_id': str(pg.ids[company]), 'user_id': str(pg.ids[client]), 'check_id': check,
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 1}],
    })


def close(pg, check, amount='798.75', role='admin_a', company='company_a'):
    return pg.client.post('/check/close', headers=pg.headers(role), json={
        'check_id': check, 'company_id': str(pg.ids[company]), 'paid_amount': amount,
    })


def get(pg, check, role='admin_a', company='company_a'):
    return pg.client.get('/check/get', headers=pg.headers(role), params={
        'check_id': check, 'company_id': str(pg.ids[company]),
    })


def ready(pg, order):
    result = status(pg, order, 'completed', 'waiter_a')
    assert result.status_code == 200, result.text


def test_self_service_separate_checks_and_atomic_rollback(pg):
    first, second = create(pg).json(), create(pg).json()
    assert first['check_id'] != second['check_id']
    assert get(pg, first['check_id']).json()['service_type'] == 'self_service'
    assert attach(pg, first['check_id']).status_code == 409
    failed = create(pg, items=[{'product_card_id': str(uuid4()), 'quantity': 1}])
    assert failed.status_code == 422
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(CheckDB)) == 2


def test_waiter_grouping_and_client_company_isolation(pg):
    mode(pg)
    first = create(pg).json()
    second = attach(pg, first['check_id'])
    assert second.status_code == 200, second.text
    check = get(pg, first['check_id']).json()
    assert check['total_amount'] == '1049.25'
    assert len(check['order_ids']) == 2
    assert attach(pg, first['check_id'], client='client_b').status_code == 404
    assert get(pg, first['check_id'], role='client_b').status_code == 404
    assert get(pg, first['check_id'], role='client_a').status_code == 200
    assert get(pg, first['check_id'], company='company_b').status_code == 404
    assert close(pg, first['check_id'], role='admin_b', company='company_b').status_code == 404
    mode(pg, 'self_service')
    assert get(pg, first['check_id']).json()['service_type'] == 'waiter_service'
    assert attach(pg, first['check_id']).status_code == 409


def test_close_exact_idempotent_and_freezes_orders(pg):
    order = create(pg).json()
    oid, cid = order['order_id'], order['check_id']
    assert close(pg, cid).status_code == 409  # not ready
    assert status(pg, oid, 'closed').status_code == 409
    ready(pg, oid)
    for amount in ('798.74', '798.76'):
        assert close(pg, cid, amount).status_code == 409
    for role in ('client_a', 'cook_a', 'admin_b'):
        assert close(pg, cid, role=role).status_code == 403
    result = close(pg, cid, role='waiter_a')
    assert result.status_code == 200, result.text
    assert result.json()['total_amount'] == result.json()['paid_amount'] == '798.75'
    assert result.json()['closed_at']
    assert close(pg, cid).json() == result.json()
    assert close(pg, cid, '0').status_code == 409
    assert read(pg, oid).json()['status'] == 'completed'
    assert pg.client.patch('/order/update_by_id', headers=pg.headers('admin_a'),
        params={'order_id': oid}, json={'comment': 'must not change'}).status_code == 409
    assert status(pg, oid, 'canceled').status_code in (409, 422)


def test_canceled_excluded_and_closed_check_rejects_new_order(pg):
    mode(pg)
    first = create(pg).json()
    second = attach(pg, first['check_id']).json()
    assert status(pg, first['order_id'], 'canceled').status_code == 200
    ready(pg, second['order_id'])
    result = close(pg, first['check_id'], '250.50')
    assert result.status_code == 200, result.text
    assert attach(pg, first['check_id']).status_code == 409


def test_missing_snapshot_and_forged_amount_rejected(pg):
    order = create(pg).json()
    ready(pg, order['order_id'])
    forged = pg.client.post('/check/close', headers=pg.headers('admin_a'), json={
        'check_id': order['check_id'], 'company_id': str(pg.ids['company_a']),
        'paid_amount': '0', 'total_amount': '0',
    })
    assert forged.status_code == 422
    with pg.engine.begin() as conn:
        conn.execute(update(OrderProductAssociationDB).where(
            OrderProductAssociationDB.order_id == UUID(order['order_id'])).values(
                unit_price=None, unit_cost_price=None, product_title=None, line_total=None))
    assert close(pg, order['check_id']).status_code == 409


def test_two_concurrent_closures_are_idempotent(pg):
    order = create(pg).json()
    ready(pg, order['order_id'])

    async def run():
        async def one():
            async with pg.sessions() as session:
                async with session.begin():
                    check = await close_check(session, UUID(order['check_id']), pg.ids['company_a'],
                                              pg.ids['admin_a'], Decimal('798.75'))
                    return check.closed_at
        return await asyncio.gather(one(), one())

    results = asyncio.run(run())
    assert results[0] == results[1]


def test_edit_waits_for_check_close_then_rejects(pg):
    order = create(pg).json()
    ready(pg, order['order_id'])

    async def run():
        async with pg.sessions() as closer:
            async with closer.begin():
                await close_check(closer, UUID(order['check_id']), pg.ids['company_a'],
                                  pg.ids['admin_a'], Decimal('798.75'))

                async def edit():
                    async with pg.sessions() as editor:
                        return await __update_order_by_id({'comment': 'late'}, UUID(order['order_id']), editor)

                task = asyncio.create_task(edit())
                try:
                    async def wait_for_lock():
                        async with pg.async_engine.connect() as observer:
                            while True:
                                waiting = await observer.scalar(text(
                                    "SELECT count(*) FROM pg_stat_activity WHERE application_name=:name "
                                    "AND wait_event_type='Lock'"), {'name': pg.schema})
                                if waiting:
                                    return
                                await asyncio.sleep(0.01)
                    await asyncio.wait_for(wait_for_lock(), 5)
                    assert not task.done()
                except BaseException:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise
            with pytest.raises(HTTPException) as error:
                await asyncio.wait_for(task, 5)
            assert error.value.status_code == 409

    asyncio.run(run())
    assert read(pg, order['order_id']).json()['comment'] == 'staff-only test note'


def test_websocket_cannot_close_preparation_instead_of_check(pg):
    order = create(pg).json()
    ready(pg, order['order_id'])
    assert close(pg, order['check_id']).status_code == 200
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as socket:
        ws_login(pg, socket, 'waiter_a')
        assert socket.receive_json()['type'] == 'ready'
        socket.send_json({'type': 'update_status', 'order_id': order['order_id'], 'status': 'closed'})
        result = socket.receive_json()
        assert result['type'] == 'error' and result['status'] == 409
    assert read(pg, order['order_id']).json()['status'] == 'completed'


def test_order_api_exposes_closed_check_status_for_history(pg):
    created = create(pg).json()
    ready(pg, created['order_id'])
    assert close(pg, created['check_id']).status_code == 200
    response = pg.client.get('/order/get_all', headers=pg.headers('admin_a'),
                             params={'company_id': str(pg.ids['company_a'])})
    assert response.status_code == 200, response.text
    item = next(row for row in response.json()['orders'] if row['order_id'] == created['order_id'])
    assert item['check_status'] == 'closed'
    assert item['status'] == 'completed'
