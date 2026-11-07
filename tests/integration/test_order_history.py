import asyncio
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from db import OrderDB, OrderStatusHistoryDB, STATUS_TYPE
from order.model_dal import OrderDal
from order.actions.update_order_action import __update_order_by_id
from tests.integration.test_order_critical_path import create, status, ws_login

pytestmark = pytest.mark.integration


def history(pg, oid, role='admin_a', company='company_a'):
    return pg.client.get('/order/status_history', headers=pg.headers(role), params={
        'order_id': oid, 'company_id': str(pg.ids[company])})


def test_history_creation_rest_socket_and_access(pg):
    response = create(pg)
    assert response.status_code == 200, response.text
    oid = response.json()['order_id']
    first = history(pg, oid)
    assert first.status_code == 200, first.text
    assert [(e['old_status'], e['new_status']) for e in first.json()] == [(None, 'created')]
    assert first.json()[0]['actor_id'] == str(pg.ids['admin_a'])
    assert pg.client.patch('/order/update_status_by_id', headers=pg.headers('cook_a'), params={
        'order_id': oid, 'new_status': 'processing', 'reason': '  Передан на кухню  '}).status_code == 200
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as ws:
        ws_login(pg, ws, 'cook_a')
        assert ws.receive_json()['type'] == 'ready'
        ws.send_json({'type': 'update_status', 'order_id': oid, 'status': 'completed', 'reason': 'Готово'})
        assert ws.receive_json()['type'] == 'order_updated'
    events = history(pg, oid).json()
    assert [(e['old_status'], e['new_status']) for e in events] == [(None, 'created'), ('created', 'processing'), ('processing', 'completed')]
    assert events[1]['reason'] == 'Передан на кухню'
    assert events[2]['reason'] == 'Готово'
    assert events[2]['actor_id'] == str(pg.ids['cook_a'])
    assert status(pg, oid, 'completed').status_code == 422
    assert len(history(pg, oid).json()) == 3
    for role, company in [('client_a', 'company_a'), ('admin_b', 'company_a'), ('admin_b', 'company_b')]:
        assert history(pg, oid, role, company).status_code == 403


def test_failure_to_write_history_rolls_back_status(pg, monkeypatch):
    oid = create(pg).json()['order_id']
    original = OrderDal.append_status_history
    async def fail(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        raise RuntimeError('audit failure')
    monkeypatch.setattr(OrderDal, 'append_status_history', fail)
    async def run():
        async with pg.sessions() as session:
            with pytest.raises(RuntimeError):
                await __update_order_by_id({'status': STATUS_TYPE.PROCESSING, 'updater_id': pg.ids['cook_a']}, UUID(oid), session,
                                          expected_status=STATUS_TYPE.CREATED)
    asyncio.run(run())
    with pg.engine.connect() as c:
        assert c.execute(select(OrderDB.status).where(OrderDB.order_id == UUID(oid))).scalar_one() == STATUS_TYPE.CREATED
        assert c.execute(select(func.count()).select_from(OrderStatusHistoryDB)).scalar_one() == 1


def test_failed_creation_and_invalid_reason_leave_no_audit_events(pg):
    assert create(pg, items=[{'product_card_id': str(uuid4()), 'quantity': 1}]).status_code == 422
    with pg.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(OrderStatusHistoryDB)).scalar_one() == 0
    oid = create(pg).json()['order_id']
    assert pg.client.patch('/order/update_status_by_id', headers=pg.headers(), params={
        'order_id': oid, 'new_status': 'processing', 'reason': 'x' * 501}).status_code == 422
    assert len(history(pg, oid).json()) == 1


def test_concurrent_status_updates_write_one_event(pg):
    oid = create(pg).json()['order_id']
    async def change():
        async with pg.sessions() as session:
            try:
                await __update_order_by_id({'status': STATUS_TYPE.PROCESSING, 'updater_id': pg.ids['cook_a']},
                    UUID(oid), session, expected_status=STATUS_TYPE.CREATED)
                return 200
            except HTTPException as exc:
                return exc.status_code
    async def run():
        return await asyncio.gather(change(), change())
    assert sorted(asyncio.run(run())) == [200, 409]
    assert len(history(pg, oid).json()) == 2
