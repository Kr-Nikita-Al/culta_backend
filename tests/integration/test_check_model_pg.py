"""Check schema, tenant isolation and legacy-safe migration on real PostgreSQL."""
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import CheckDB, OrderDB
from test_order_critical_path import create

pytestmark = pytest.mark.integration


def make_check(pg):
    with Session(pg.engine) as session, session.begin():
        check = CheckDB(company_id=pg.ids['company_a'], user_id=pg.ids['client_a'],
                        creator_id=pg.ids['admin_a'], updater_id=pg.ids['admin_a'])
        session.add(check)
        session.flush()
        assert check.status == 'open' and check.total_amount is None
        assert check.paid_amount == Decimal('0.00')
        return check.check_id


def test_check_groups_orders_and_preserves_exact_payment(pg):
    check_id = make_check(pg)
    ids = [UUID(create(pg).json()['order_id']) for _ in range(2)]
    with Session(pg.engine) as session, session.begin():
        for oid in ids:
            session.get(OrderDB, oid).check_id = check_id
        session.flush()
        check = session.get(CheckDB, check_id)
        assert {o.order_id for o in check.orders} == set(ids)
        check.total_amount = Decimal('1597.50')
        check.paid_amount = Decimal('0.10')
    with Session(pg.engine) as session:
        check = session.get(CheckDB, check_id)
        assert check.paid_amount == Decimal('0.10')
        assert check.total_amount == Decimal('1597.50')


@pytest.mark.parametrize('field,value', [('company_id', 'company_b'), ('user_id', 'client_b')])
def test_database_rejects_cross_company_or_cross_client_order(pg, field, value):
    check_id = make_check(pg)
    oid = create(pg).json()['order_id']
    with pytest.raises(IntegrityError), pg.engine.begin() as connection:
        connection.execute(text(f'UPDATE orders SET check_id=:cid, {field}=:value WHERE order_id=:oid'),
                           {'cid': check_id, 'value': pg.ids[value], 'oid': oid})


@pytest.mark.parametrize('assignment', [
    'paid_amount=-1', "paid_amount='NaN'", 'total_amount=-1', "total_amount='NaN'",
    "status='unknown'", "status='closed'", 'total_amount=1, paid_amount=2',
    "closed_at=now()", "status='closed', closed_at=now()",
])
def test_financial_constraints(pg, assignment):
    make_check(pg)
    with pytest.raises(IntegrityError), pg.engine.begin() as connection:
        connection.execute(text('UPDATE checks SET ' + assignment))


def test_closed_check_and_delete_protection(pg):
    check_id = make_check(pg)
    oid = create(pg).json()['order_id']
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE orders SET check_id=:cid WHERE order_id=:oid'), {'cid': check_id, 'oid': oid})
        connection.execute(text("UPDATE checks SET status='closed', total_amount=798.75, paid_amount=798.75, closed_at=now()"))
    with pytest.raises(IntegrityError), pg.engine.begin() as connection:
        connection.execute(text('DELETE FROM checks WHERE check_id=:cid'), {'cid': check_id})


def test_check_requires_existing_references(pg):
    with pytest.raises(IntegrityError), Session(pg.engine) as session, session.begin():
        session.add(CheckDB(company_id=uuid4(), user_id=pg.ids['client_a'],
                            creator_id=pg.ids['admin_a'], updater_id=pg.ids['admin_a']))
        session.flush()


@pytest.mark.parametrize('pg', ['e49e37c102a8'], indirect=True)
def test_migration_preserves_legacy_orders_without_inventing_checks(pg):
    oid = pg.ids['legacy_order']
    command.upgrade(pg.migration_config, 'head')
    with pg.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM checks')).scalar_one() == 0
        assert connection.execute(text('SELECT check_id, price FROM orders WHERE order_id=:oid'),
                                  {'oid': oid}).one() == (None, Decimal('798.75'))
