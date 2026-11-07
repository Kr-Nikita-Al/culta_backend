"""Guest financial history, isolation, atomic linking and no synthetic accounts."""
import pytest
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from db import UserDB, CheckDB, OrderDB, UserRoleDB
from utils.constants import EMPTY_UUID
from checks.service import close_check, link_guest
from tests.integration.test_check_api import mode, ready, close, get
from user.actions.qr_code_action import generate_jwt_qr_data

pytestmark = pytest.mark.integration


def guest(pg, **changes):
    return pg.client.post('/order/create', headers=pg.headers('admin_a'), json={
        'company_id': str(pg.ids['company_a']), 'guest_name': 'Гость Анна',
        'order_items': [{'product_card_id': str(pg.ids['product_a']), 'quantity': 1}], **changes})


def link(pg, check_id, role='admin_a'):
    return pg.client.post('/check/link_guest', headers=pg.headers(role), json={
        'company_id': str(pg.ids['company_a']), 'check_id': check_id,
        'qr_token': generate_jwt_qr_data(str(pg.ids['client_a']))})


def test_guest_paid_without_account_or_bonuses(pg):
    with pg.engine.connect() as conn:
        before = conn.scalar(select(func.count()).select_from(UserDB))
        wallets = conn.execute(select(UserDB.user_id, UserDB.bonus_balance).order_by(UserDB.user_id)).all()
    response = guest(pg)
    assert response.status_code == 200, response.text
    order = response.json()
    assert order['user_id'] is None
    cid = order['check_id']
    result = get(pg, cid)
    assert result.status_code == 200, result.text
    assert result.json()['guest_name'] == 'Гость Анна'
    assert result.json()['bonus_balance'] is None
    assert get(pg, cid, role='client_a').status_code == 404
    ready(pg, order['order_id'])
    assert close(pg, cid, '250.49').status_code == 409
    rejected = pg.client.post('/check/close', headers=pg.headers('admin_a'), json={
        'company_id': str(pg.ids['company_a']), 'check_id': cid, 'paid_amount': '249.50', 'bonus_spent':'1'})
    assert rejected.status_code == 409
    paid = close(pg, cid, '250.50')
    assert paid.status_code == 200, paid.text
    assert paid.json()['bonus_earned'] == paid.json()['bonus_spent'] == '0.00'
    assert close(pg, cid, '250.50').json() == paid.json()
    assert link(pg, cid).status_code == 409
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(UserDB)) == before
        assert conn.execute(select(UserDB.user_id, UserDB.bonus_balance).order_by(UserDB.user_id)).all() == wallets


def test_link_moves_all_orders_and_rejects_guest_additions(pg):
    mode(pg)
    first = guest(pg).json()
    second = guest(pg, check_id=first['check_id'])
    assert second.status_code == 200, second.text
    for role in ('client_a', 'cook_a', 'admin_b'):
        assert link(pg, first['check_id'], role).status_code == 403
    linked = link(pg, first['check_id'])
    assert linked.status_code == 200, linked.text
    assert linked.json()['user_id'] == str(pg.ids['client_a'])
    assert len(linked.json()['order_ids']) == 2
    assert linked.json()['bonus_balance'] is not None
    with pg.engine.connect() as conn:
        assert set(conn.scalars(select(OrderDB.user_id))) == {pg.ids['client_a']}
    assert guest(pg, check_id=first['check_id']).status_code == 404
    assert get(pg, first['check_id'], role='client_a').status_code == 200
    ready(pg, first['order_id']); ready(pg, second.json()['order_id'])
    assert close(pg, first['check_id'], '501.00').status_code == 200


def test_null_client_cannot_bypass_database_scope(pg):
    order = guest(pg).json()
    with pytest.raises(IntegrityError), pg.engine.begin() as conn:
        conn.execute(update(OrderDB).where(OrderDB.order_id == order['order_id']).values(company_id=pg.ids['company_b']))
    with pytest.raises(IntegrityError), pg.engine.begin() as conn:
        conn.execute(update(CheckDB).where(CheckDB.check_id == order['check_id']).values(user_id=pg.ids['client_a']))
    with pytest.raises(IntegrityError), pg.engine.begin() as conn:
        conn.execute(update(CheckDB).where(CheckDB.check_id == order['check_id']).values(bonus_earned=10))


def test_open_lists_and_client_lookup_are_staff_only(pg):
    mode(pg)
    order = guest(pg).json()
    params = {'company_id':str(pg.ids['company_a'])}
    for path in ('/check/open', '/check/tables', '/check/clients'):
        assert pg.client.get(path, params=params, headers=pg.headers('client_a')).status_code == 403
    result = pg.client.get('/check/open', params=params, headers=pg.headers('waiter_a'))
    assert result.status_code == 200, result.text
    assert result.json()[0]['check_id'] == order['check_id']
    lookup = pg.client.get('/check/clients', params={**params, 'query':'client_a@example.test'}, headers=pg.headers('admin_a'))
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()[0]['user_id'] == str(pg.ids['client_a'])
    assert set(lookup.json()[0]) == {'user_id','name','surname'}
    denied = pg.client.post('/order/create', headers=pg.headers('client_a'), json={
        'company_id':str(pg.ids['company_a']), 'user_id':None,
        'order_items':[{'product_card_id':str(pg.ids['product_a']), 'quantity':1}]})
    assert denied.status_code == 403


def test_guest_revenue_not_counted_as_registered_client(pg):
    order = guest(pg).json()
    ready(pg, order['order_id'])
    assert close(pg, order['check_id'], '250.50').status_code == 200
    with Session(pg.engine) as session, session.begin():
        session.add(UserRoleDB(user_id=pg.ids['admin_a'],company_id=EMPTY_UUID,role='PORTAL_ROLE_SUPER_ADMIN'))
    day = datetime.now(timezone.utc).date().isoformat()
    result = pg.client.get('/admin/statistics', params={'date_from':day,'date_to':day},headers=pg.headers('admin_a'))
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['totals']['revenue'] == '250.50'
    assert data['totals']['orders'] == 1
    assert data['users']['total'] == 6
    assert data['users']['active_buyers'] == 0


def test_concurrent_link_and_close_are_consistent(pg):
    from uuid import UUID
    order = guest(pg).json()
    ready(pg, order['order_id'])
    cid = UUID(order['check_id'])
    async def exercise():
        async def operation(linking):
            try:
                async with pg.sessions() as db, db.begin():
                    if linking:
                        await link_guest(db,cid,pg.ids['company_a'],pg.ids['client_a'],pg.ids['admin_a'])
                    else:
                        await close_check(db,cid,pg.ids['company_a'],pg.ids['admin_a'],Decimal('250.50'))
                return 200
            except HTTPException as exc:
                return exc.status_code
        return await asyncio.wait_for(asyncio.gather(operation(True),operation(False)),timeout=10)
    results = asyncio.run(exercise())
    assert all(code in (200,409) for code in results)
    assert 200 in results
    with Session(pg.engine) as db:
        check = db.get(CheckDB,cid)
        assert db.get(OrderDB,UUID(order['order_id'])).user_id == check.user_id
        if check.user_id is None:
            assert check.bonus_earned == check.bonus_spent == 0
