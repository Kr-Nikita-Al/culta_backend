"""Mobile client ordering uses real migrations, authentication and transactions."""
import asyncio
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from db import CompanyDB, DiningTableDB, OrderDB, CheckDB, UserDB, OrderProductAssociationDB
from utils.constants import EMPTY_UUID

pytestmark = pytest.mark.integration


@pytest.fixture
def client_setup(pg):
    with Session(pg.engine) as session, session.begin():
        session.execute(update(CompanyDB).values(allow_client_orders_inside=True,
            allow_client_orders_outside=True, work_state=True))
        for key, company in [('table_a', 'company_a'), ('table_a2', 'company_a'), ('table_b', 'company_b')]:
            pg.ids[key] = uuid4()
            session.add(DiningTableDB(table_id=pg.ids[key], company_id=pg.ids[company],
                label=key, shape='square', seats=4, x=100, y=100, width=80, height=80))
    return pg


def issue(pg, table='table_a', company='company_a', role='admin_a'):
    return pg.client.post('/order/table-qr', headers=pg.headers(role), json={
        'company_id': str(pg.ids[company]), 'table_id': str(pg.ids[table])})


def body(pg, **kwargs):
    return {'company_id': str(pg.ids['company_a']), 'request_id': str(uuid4()), 'context': 'outside',
            'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 2}], **kwargs}


def create(pg, data, role='client_a'):
    return pg.client.post('/order/create-client', headers=pg.headers(role), json=data)


def count(pg, model):
    with pg.engine.connect() as conn:
        return conn.scalar(select(func.count()).select_from(model))


def test_outside_identity_totals_history_and_replay(client_setup, monkeypatch):
    pg = client_setup
    notify = AsyncMock()
    monkeypatch.setattr('order.api_handlers._notify_new_order', notify)
    data = body(pg)
    response = create(pg, data)
    assert response.status_code == 200, response.text
    order = response.json()
    assert order['user_id'] == str(pg.ids['client_a'])
    assert order['price'] == '501.00' and order['order_context'] == 'outside'
    assert order['table_id'] is None and not order['replayed']
    assert not {'staff_id', 'comment', 'creator_id', 'updater_id', 'cost_price'} & order.keys()
    with pg.engine.begin() as conn:
        assert conn.scalar(select(OrderDB.staff_id)) == EMPTY_UUID
        conn.execute(update(OrderDB).values(comment='Staff-only note'))
    retry = create(pg, data)
    assert retry.status_code == 200 and retry.json()['replayed']
    assert 'comment' not in retry.json()
    assert retry.json()['order_id'] == order['order_id']
    notify.assert_awaited_once()
    assert count(pg, OrderDB) == count(pg, CheckDB) == 1
    assert create(pg, {**data, 'comment': 'different'}).status_code == 409


def test_inside_qr_resolution_rotation_and_company_scope(client_setup):
    pg = client_setup
    issued = issue(pg)
    assert issued.status_code == 200 and issued.headers['cache-control'] == 'no-store'
    token = issued.json()['table_token']
    resolution = {'company_id': str(pg.ids['company_a']), 'table_token': token}
    resolved = pg.client.post('/order/resolve-table', headers=pg.headers('client_a'), json=resolution)
    assert resolved.status_code == 200 and resolved.json()['can_order']
    data = body(pg, context='inside', table_token=token)
    order = create(pg, data)
    assert order.status_code == 200, order.text
    assert order.json()['table_id'] == str(pg.ids['table_a'])
    with pg.engine.connect() as conn:
        assert conn.scalar(select(CheckDB.table_id)) == pg.ids['table_a']
    assert create(pg, body(pg, context='inside', table_token=token + 'x')).status_code == 403
    other = issue(pg, 'table_b', 'company_b', 'admin_b').json()['table_token']
    assert create(pg, body(pg, context='inside', table_token=other)).status_code == 403
    assert issue(pg).status_code == 200
    assert create(pg, body(pg, context='inside', table_token=token)).status_code == 403
    # A retry retrieves an existing order even after revocation, never creates another.
    assert create(pg, data).json()['order_id'] == order.json()['order_id']
    assert count(pg, OrderDB) == 1


@pytest.mark.parametrize('role', ['client_a', 'waiter_a', 'cook_a', 'admin_b'])
def test_qr_management_roles(client_setup, role):
    assert issue(client_setup, role=role).status_code == 403


@pytest.mark.parametrize('field,value', [('allow_client_orders_outside', False), ('work_state', False), ('is_active', False)])
def test_company_blocks_orders_atomically(client_setup, field, value):
    pg = client_setup
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).where(CompanyDB.company_id == pg.ids['company_a']).values({field: value}))
    assert create(pg, body(pg)).status_code in (403, 404)
    assert count(pg, OrderDB) == count(pg, CheckDB) == 0


def test_inside_setting_and_inactive_table(client_setup):
    pg = client_setup
    token = issue(pg).json()['table_token']
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).values(allow_client_orders_inside=False))
    assert create(pg, body(pg, context='inside', table_token=token)).status_code == 403
    assert create(pg, body(pg)).status_code == 200
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).values(allow_client_orders_inside=True))
        conn.execute(update(DiningTableDB).values(is_active=False))
    assert create(pg, body(pg, context='inside', table_token=token)).status_code == 403


@pytest.mark.parametrize('extra', [{'user_id': str(uuid4())}, {'staff_id': str(uuid4())}, {'price': '0'},
                                  {'context': 'inside'}, {'order_items': []}])
def test_client_cannot_override_identity_price_or_context(client_setup, extra):
    pg = client_setup
    assert create(pg, body(pg, **extra)).status_code == 422
    assert count(pg, OrderDB) == count(pg, CheckDB) == 0


def test_bad_product_rolls_back_and_request_can_retry(client_setup):
    pg = client_setup
    data = body(pg)
    data['order_items'].append({'product_card_id': str(pg.ids['product_b']), 'quantity': 1})
    assert create(pg, data).status_code == 422
    assert count(pg, OrderDB) == count(pg, CheckDB) == count(pg, OrderProductAssociationDB) == 0
    data['order_items'].pop()
    assert create(pg, data).status_code == 200


def test_check_service_mode_and_visit_isolation(client_setup):
    pg = client_setup
    first = create(pg, body(pg)).json()
    assert create(pg, body(pg, check_id=first['check_id'])).status_code == 409
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).values(service_type='waiter_service'))
    token = issue(pg).json()['table_token']
    inside = body(pg, context='inside', table_token=token)
    first = create(pg, inside).json()
    cid = first['check_id']
    assert create(pg, body(pg, context='inside', table_token=token, check_id=cid)).status_code == 200
    staff_order = pg.client.post('/order/create', headers=pg.headers('admin_a'), json={
        'company_id': str(pg.ids['company_a']), 'user_id': str(pg.ids['client_a']), 'check_id': cid,
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 1}]})
    assert staff_order.status_code == 200, staff_order.text
    assert staff_order.json()['table_id'] == str(pg.ids['table_a'])
    assert staff_order.json()['order_context'] == 'inside'
    assert create(pg, body(pg, check_id=cid)).status_code == 409
    token2 = issue(pg, 'table_a2').json()['table_token']
    assert create(pg, body(pg, context='inside', table_token=token2, check_id=cid)).status_code == 409
    assert create(pg, body(pg, context='inside', table_token=token, check_id=cid), 'client_b').status_code == 404
    with pg.engine.begin() as conn:
        conn.execute(update(CheckDB).where(CheckDB.check_id == UUID(cid)).values(status='canceled'))
    assert create(pg, body(pg, context='inside', table_token=token, check_id=cid)).status_code == 409


def test_inactive_user_and_missing_auth(client_setup):
    pg = client_setup
    headers = pg.headers('client_a')
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id == pg.ids['client_a']).values(is_active=False))
    assert pg.client.post('/order/create-client', headers=headers, json=body(pg)).status_code == 403
    assert pg.client.post('/order/create-client', json=body(pg)).status_code == 401


def test_concurrent_retries_create_one_order(client_setup):
    from order.actions.create_order_action import __create_order
    from order.interface_request import CreateOrderRequest
    from order.client_schemas import ClientOrderRequest
    pg = client_setup
    request = ClientOrderRequest(**body(pg))
    internal = CreateOrderRequest(company_id=request.company_id, user_id=pg.ids['client_a'],
        comment='', cocking_time=0, order_items=request.order_items)

    async def run():
        async def send():
            async with pg.sessions() as session:
                return await __create_order(internal, pg.ids['client_a'], session, client_request=request)
        return await asyncio.gather(send(), send())
    results = asyncio.run(run())
    assert results[0].order_id == results[1].order_id
    assert sorted(result.replayed for result in results) == [False, True]
    assert count(pg, OrderDB) == count(pg, CheckDB) == 1
