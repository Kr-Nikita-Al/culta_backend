from decimal import Decimal
from uuid import UUID
import pytest
from sqlalchemy import select
from db import CompanyDB, CheckDB
from tests.integration.test_order_critical_path import create
from tests.integration.test_check_api import ready, close, get, ws_login

pytestmark = pytest.mark.integration


def config(pg):
    return pg.client.get('/company/infrastructure', params={'company_id':str(pg.ids['company_a'])}, headers=pg.headers()).json()


def save(pg, data, role='admin_a'):
    return pg.client.put('/company/infrastructure', params={'company_id':str(pg.ids['company_a'])}, headers=pg.headers(role), json=data)


def test_rates_permissions_and_version(pg):
    data = config(pg)
    assert save(pg, data, 'admin_b').status_code == 403
    assert save(pg, {**data, 'bonus_payment_perc':'0', 'bonus_accrual_perc':'1'}).status_code == 422
    updated = {**data, 'bonus_payment_perc':'20', 'bonus_accrual_perc':'10'}
    assert save(pg, updated).status_code == 200
    assert save(pg, data).status_code == 409
    result = pg.client.patch('/company/update_by_id', params={'company_id':str(pg.ids['company_a'])},
        headers=pg.headers(), json={'bonus_payment_perc':'5'})
    assert result.status_code == 422
    assert config(pg)['bonus_payment_perc'] == '20.00'


def test_next_check_level_cash_only_and_snapshot(pg):
    data = config(pg)
    data.update(bonus_payment_perc='20', bonus_accrual_perc='5', levels=[{
        'name':'Постоянный гость', 'threshold':'798.75', 'bonus_payment_perc':'30', 'bonus_accrual_perc':'10'}])
    assert save(pg, data).status_code == 200
    first = create(pg).json(); ready(pg, first['order_id'])
    response = close(pg, first['check_id'])
    assert response.status_code == 200, response.text
    assert response.json()['loyalty_level_name'] is None
    assert response.json()['bonus_earned'] == '39.93'
    second = create(pg).json(); ready(pg, second['order_id'])
    preview = get(pg, second['check_id']).json()
    assert preview['loyalty_level_name'] == 'Постоянный гость'
    assert preview['bonus_accrual_perc'] == '10.00'
    assert close(pg, second['check_id']).json()['bonus_earned'] == '79.87'
    changed = config(pg); changed['levels'] = []
    assert save(pg, changed).status_code == 200
    assert get(pg, second['check_id']).json()['loyalty_level_name'] == 'Постоянный гость'
    with pg.engine.connect() as conn:
        assert conn.scalar(select(CompanyDB.loyalty_levels).where(CompanyDB.company_id==pg.ids['company_b'])) == []


def test_disabled_sections_and_reenable_preserves_orders(pg):
    order = create(pg).json()
    data = config(pg); data.update(orders_enabled=False, reservations_enabled=False, images_enabled=False)
    assert save(pg, data).status_code == 200
    assert pg.client.get('/order/get_by_id', headers=pg.headers(), params={'order_id':order['order_id']}).status_code == 403
    assert pg.client.get('/check/get', headers=pg.headers(), params={'check_id':order['check_id'], 'company_id':str(pg.ids['company_a'])}).status_code == 403
    response = pg.client.get('/reservations/board', headers=pg.headers(), params={
        'company_id':str(pg.ids['company_a']), 'starts_at':'2030-01-01T12:00:00Z', 'ends_at':'2030-01-01T13:00:00Z'})
    assert response.status_code == 403
    from starlette.websockets import WebSocketDisconnect
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as socket:
        ws_login(pg, socket, 'admin_a')
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    data = config(pg); data.update(orders_enabled=True, reservations_enabled=True, images_enabled=True)
    assert save(pg, data).status_code == 200
    assert get(pg, order['check_id']).status_code == 200


@pytest.mark.parametrize('levels', [
    [{'name':'A','threshold':'1','bonus_payment_perc':'5','bonus_accrual_perc':'6'}],
    [{'name':'A','threshold':'1','bonus_payment_perc':'5','bonus_accrual_perc':'1'},
     {'name':'B','threshold':'1.00','bonus_payment_perc':'5','bonus_accrual_perc':'1'}],
])
def test_invalid_levels(pg, levels):
    assert save(pg, {**config(pg), 'levels':levels}).status_code == 422
