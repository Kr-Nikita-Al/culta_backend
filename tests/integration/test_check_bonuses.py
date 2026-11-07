import asyncio
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select, update, func
from db import CompanyDB, UserDB, CheckDB, BonusTransactionDB
from checks.service import close_check
from tests.integration.test_order_critical_path import create
from tests.integration.test_check_api import ready, get

pytestmark = pytest.mark.integration


def setup(pg, payment=20, accrual=10):
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).values(bonus_payment_perc=payment, bonus_accrual_perc=accrual))
    order = create(pg).json()
    ready(pg, order['order_id'])
    return order['check_id']


def close(pg, check, paid='699.00', spent='99.75'):
    return pg.client.post('/check/close', headers=pg.headers(), json={
        'check_id': check, 'company_id': str(pg.ids['company_a']), 'paid_amount': paid, 'bonus_spent': spent})


def wallet(pg):
    with pg.engine.connect() as conn:
        return conn.scalar(select(UserDB.bonus_balance).where(UserDB.user_id == pg.ids['client_a']))


def test_exact_settlement_replay_snapshot_and_privacy(pg):
    check = setup(pg)
    preview = get(pg, check).json()
    assert preview['max_bonus_spend'] == '159.75'
    assert preview['bonus_balance'] == '500.00'
    assert get(pg, check, role='cook_a').json()['bonus_balance'] is None
    result = close(pg, check)
    assert result.status_code == 200, result.text
    assert result.json()['bonus_earned'] == '69.90'
    assert result.json()['bonus_spent'] == '99.75'
    assert wallet(pg) == Decimal('470.15')
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).values(bonus_payment_perc=0, bonus_accrual_perc=0))
    assert close(pg, check).json() == result.json()
    assert close(pg, check, '698.75', '100').status_code == 409
    with pg.engine.connect() as conn:
        entries = conn.execute(select(BonusTransactionDB).where(BonusTransactionDB.check_id == UUID(check))).all()
        assert len(entries) == 2
        assert {row.kind for row in entries} == {'accrual', 'redemption'}


@pytest.mark.parametrize('paid,spent', [('638.99', '159.75'), ('639', '159.76'), ('0', '798.75')])
def test_reject_limits_or_incorrect_payment_without_writes(pg, paid, spent):
    check = setup(pg)
    assert close(pg, check, paid, spent).status_code == 409
    assert wallet(pg) == Decimal('500')
    assert get(pg, check).json()['status'] == 'open'
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(BonusTransactionDB)) == 0


def test_concurrent_same_check_and_rollback(pg):
    check = setup(pg)
    async def one(rollback=False):
        async with pg.sessions() as session:
            row = await close_check(session, UUID(check), pg.ids['company_a'], pg.ids['admin_a'],
                                    Decimal('699'), Decimal('99.75'))
            timestamp = row.closed_at
            await (session.rollback() if rollback else session.commit())
            return timestamp
    async def run():
        await one(rollback=True)
        return await asyncio.gather(one(), one())
    timestamps = asyncio.run(run())
    assert timestamps[0] == timestamps[1]
    assert wallet(pg) == Decimal('470.15')


def test_different_checks_cannot_overspend_shared_wallet(pg):
    first = setup(pg, payment=100, accrual=0)
    second = setup(pg, payment=100, accrual=0)
    async def one(check):
        from fastapi import HTTPException
        async with pg.sessions() as session:
            try:
                await close_check(session, UUID(check), pg.ids['company_a'], pg.ids['admin_a'],
                                  Decimal('398.75'), Decimal('400'))
                await session.commit()
                return 200
            except HTTPException as error:
                await session.rollback()
                return error.status_code
    async def run():
        return await asyncio.gather(one(first), one(second))
    assert sorted(asyncio.run(run())) == [200, 409]
    assert wallet(pg) == Decimal('100')


def test_zero_percent_and_round_down(pg):
    check = setup(pg, payment=1, accrual=1)
    result = close(pg, check, '798.75', '0')
    assert result.status_code == 200, result.text
    assert result.json()['bonus_earned'] == '7.98'
    assert wallet(pg) == Decimal('507.98')
