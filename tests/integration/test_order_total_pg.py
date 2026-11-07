import asyncio
from uuid import UUID

import pytest
from sqlalchemy import text

from db import STATUS_TYPE
from order.actions.update_order_action import __update_order_by_id
from order.interface_request.create_order_request import OrderProductItem
from test_order_critical_path import create, read, ws_login
from order.order_product_association.actions.create_order_product_action import __create_order_product_action
from order.order_product_association.actions.update_order_product_action import __update_order_product_action
from order.order_product_association.interface_request import CreateOrderProductRequest

pytestmark = pytest.mark.integration


def patch(pg, oid, items, **fields):
    return pg.client.patch('/order/update_by_id', headers=pg.headers(), params={'order_id': oid},
                           json={'order_items': items, **fields})


def item(pg, key, quantity):
    return {'product_card_id': str(pg.ids[key]), 'quantity': quantity}


def test_total_uses_all_snapshots_and_committed_ws_payload(pg):
    oid = create(pg).json()['order_id']
    other = create(pg).json()['order_id']
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=999, cost_price=888'))
    with pg.client.websocket_connect(f'/ws/orders/ws/client/{oid}') as client:
        ws_login(pg, client, 'client_a')
        assert client.receive_json()['price'] == '798.75'
        response = patch(pg, oid, [item(pg, 'product_a', 3)])
        assert response.status_code == 200, response.text
        assert client.receive_json()['order']['price'] == '1049.25'
    saved = read(pg, oid).json()
    assert saved['price'] == '1049.25'
    assert read(pg, other).json()['price'] == '798.75'
    assert patch(pg, oid, [item(pg, 'product_a', 0), item(pg, 'product_a2', 0)]).status_code == 200
    assert read(pg, oid).json()['price'] == '0.00'


def test_total_overflow_rolls_back_positions_comment_and_notification(pg):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=3000000000000000'))
    oid = create(pg, items=[item(pg, 'product_a', 1), item(pg, 'product_a2', 1)]).json()['order_id']
    before = read(pg, oid).json()
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as staff:
        ws_login(pg, staff, 'admin_a')
        assert staff.receive_json()['type'] == 'ready'
        response = patch(pg, oid, [item(pg, 'product_a', 2), item(pg, 'product_a2', 2)], comment='must roll back')
        assert response.status_code == 422, response.text
        staff.send_json({'type': 'unsupported'})
        assert staff.receive_json()['type'] == 'error'
    assert read(pg, oid).json() == before


def test_concurrent_quantity_changes_do_not_lose_total(pg):
    oid = UUID(create(pg).json()['order_id'])

    async def edit(key, quantity):
        async with pg.sessions() as session:
            await __update_order_by_id({}, oid, session,
                order_items=[OrderProductItem(product_card_id=pg.ids[key], quantity=quantity)],
                expected_status=STATUS_TYPE.CREATED)

    async def scenario():
        await asyncio.gather(edit('product_a', 3), edit('product_a2', 4))

    asyncio.run(scenario())
    assert read(pg, str(oid)).json()['price'] == '1148.50'


def test_caller_cannot_set_total(pg):
    oid = create(pg).json()['order_id']
    response = patch(pg, oid, [item(pg, 'product_a', 3)], price='0.01')
    assert response.status_code == 422
    assert read(pg, oid).json()['price'] == '798.75'


def test_internal_position_actions_keep_order_total_consistent(pg):
    oid = UUID(create(pg, items=[]).json()['order_id'])

    async def scenario():
        async with pg.sessions() as session:
            created = await __create_order_product_action(CreateOrderProductRequest(
                order_id=oid, product_card_id=pg.ids['product_a'], quantity=2), session)
        with pg.engine.connect() as connection:
            assert str(connection.execute(text('SELECT price FROM orders WHERE order_id=:id'), {'id': oid}).scalar_one()) == '501.00'
        async with pg.sessions() as session:
            updated = await __update_order_product_action(oid, pg.ids['product_a'], {'quantity': 3}, session)
        assert updated == created.id

    asyncio.run(scenario())
    assert read(pg, str(oid)).json()['price'] == '751.50'
