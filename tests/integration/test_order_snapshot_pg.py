"""Real historical positions, migration, REST and WS privacy on PostgreSQL."""
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from test_order_critical_path import create, read, ws_login, status

pytestmark = pytest.mark.integration


def change_catalog(pg):
    with pg.engine.begin() as connection:
        connection.execute(text("UPDATE product_card SET title='Changed', price=999, cost_price=888, is_active=false"))


def position(pg, oid, role='admin_a', company='company_a'):
    response = read(pg, oid, role, company)
    assert response.status_code == 200, response.text
    return next(item for item in response.json()['order_items']
                if item['product_card_id'] == str(pg.ids['product_a']))


def test_snapshot_survives_catalog_changes_and_quantity_update(pg):
    oid = create(pg).json()['order_id']
    before = position(pg, oid)
    assert before['snapshot_available'] is True
    assert (before['product_title'], before['unit_price'], before['unit_cost_price'], before['line_total']) == (
        'product_a', '250.50', '10.00', '501.00')
    change_catalog(pg)
    after = position(pg, oid)
    for field in ('product_title', 'unit_price', 'unit_cost_price', 'line_total', 'quantity'):
        assert after[field] == before[field]
    assert after['product_info']['title'] == 'product_a'
    assert after['product_info']['price'] == '250.50'
    assert after['product_info']['cost_price'] == '10.00'

    response = pg.client.patch('/order/update_by_id', headers=pg.headers(), params={'order_id': oid}, json={
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 3,
                         'unit_price': '0.01', 'product_title': 'Forged', 'line_total': '0.03'}]})
    assert response.status_code == 200, response.text
    updated = position(pg, oid)
    assert updated['unit_price'] == '250.50' and updated['line_total'] == '751.50'
    assert updated['unit_cost_price'] == '10.00' and updated['product_title'] == 'product_a'
    with pg.engine.connect() as connection:
        row = connection.execute(text('SELECT unit_price, line_total FROM order_product_association WHERE order_id=:oid AND product_card_id=:pid'),
                                 {'oid': oid, 'pid': pg.ids['product_a']}).one()
        assert row == (Decimal('250.50'), Decimal('751.50'))


def test_rest_and_websocket_keep_cost_staff_only(pg):
    oid = create(pg).json()['order_id']
    change_catalog(pg)
    public = read(pg, oid, 'client_a', None)
    assert 'cost_price' not in public.text
    assert position(pg, oid, 'client_a', None)['unit_price'] == '250.50'
    with pg.client.websocket_connect(f'/ws/orders/ws/client/{oid}') as client:
        ws_login(pg, client, 'client_a')
        initial = client.receive_json()
        assert initial['type'] == 'initial_status'
        assert 'cost_price' not in str(initial)
        assert initial['order_items'][0]['snapshot_available'] is True
        assert status(pg, oid, 'processing').status_code == 200
        event = client.receive_json()
        assert event['type'] == 'status_changed'
        assert 'cost_price' not in str(event)
        assert {item['unit_price'] for item in event['order']['order_items']} == {'250.50', '99.25'}


@pytest.mark.parametrize('pg', ['d82e91b6a704'], indirect=True)
def test_legacy_migration_does_not_invent_history(pg):
    oid = pg.ids['legacy_order']
    change_catalog(pg)
    command.upgrade(pg.migration_config, 'head')
    # These fixture users must be confirmed explicitly before exercising the API.
    with pg.engine.begin() as connection:
        connection.execute(text("UPDATE \"user\" SET account_status='confirmed'"))
    item = position(pg, oid)
    assert item['snapshot_available'] is False
    assert all(item[field] is None for field in ('product_title', 'unit_price', 'unit_cost_price', 'line_total'))
    assert item['quantity'] == 2
    assert read(pg, oid).json()['price'] == '798.75'
    response = pg.client.patch('/order/update_by_id', headers=pg.headers(), params={'order_id': oid}, json={
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 3}]})
    assert response.status_code == 409, response.text
    assert position(pg, oid)['line_total'] is None
    assert position(pg, oid)['quantity'] == 2
    metadata = pg.client.patch('/order/update_by_id', headers=pg.headers(), params={'order_id': oid}, json={'comment': 'Legacy note'})
    assert metadata.status_code == 200, metadata.text
    assert read(pg, oid).json()['price'] == '798.75'


@pytest.mark.parametrize('assignment', ['line_total=1', 'unit_cost_price=-1', "unit_price='NaN'", 'product_title=NULL'])
def test_snapshot_consistency_enforced_by_database(pg, assignment):
    create(pg)
    with pytest.raises(IntegrityError), pg.engine.begin() as connection:
        connection.execute(text(f'UPDATE order_product_association SET {assignment}'))


def test_snapshot_overflow_rolls_back_earlier_position_edit(pg):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=5000000000000000 WHERE product_card_id=:id'), {'id': pg.ids['product_a2']})
    response = create(pg, items=[{'product_card_id': str(pg.ids['product_a']), 'quantity': 1},
                                {'product_card_id': str(pg.ids['product_a2']), 'quantity': 1}])
    assert response.status_code == 200, response.text
    oid = response.json()['order_id']
    response = pg.client.patch('/order/update_by_id', headers=pg.headers(), params={'order_id': oid}, json={
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 3},
                        {'product_card_id': str(pg.ids['product_a2']), 'quantity': 2}]})
    assert response.status_code == 422, response.text
    item = position(pg, oid)
    assert item['quantity'] == 1 and item['line_total'] == '250.50'


def test_zero_quantity_preserves_snapshot(pg):
    oid = create(pg).json()['order_id']
    response = pg.client.patch('/order/update_by_id', headers=pg.headers(), params={'order_id': oid}, json={
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 0}]})
    assert response.status_code == 200, response.text
    item = position(pg, oid)
    assert item['line_total'] == '0.00' and item['unit_price'] == '250.50'
