import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, update, text, func
from sqlalchemy.exc import DBAPIError
from db import UserDB, CompanyDB, BonusTransactionDB
from bonuses.service import adjust_balance, record_initial
from user.model_dal import UserDAL
from user.interface_request import UpdateBonusBalanceRequest

pytestmark = pytest.mark.integration


def payload(pg, **extra):
    return dict(company_id=str(pg.ids['company_a']), request_id=str(uuid4()),
                reason='Correction', amount='10.00', is_write_off=False, **extra)


def enable(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(CompanyDB).values(bonus_accrual_perc=10, bonus_payment_perc=20))


def post(pg, data, role='admin_a'):
    return pg.client.patch('/user/update_bonus_balance_by_id', params={'user_id': str(pg.ids['client_a'])},
                           headers=pg.headers(role), json=data)


def balance(pg):
    with pg.engine.connect() as conn:
        return conn.scalar(select(UserDB.bonus_balance).where(UserDB.user_id == pg.ids['client_a']))


def test_correction_replay_conflict_history_and_permissions(pg):
    enable(pg)
    data = payload(pg)
    for role in ['waiter_a', 'cook_a', 'client_a', 'admin_b']:
        assert post(pg, data, role).status_code == 403
    assert post(pg, data).status_code == 200
    assert post(pg, data).status_code == 200
    assert post(pg, {**data, 'amount': '11'}).status_code == 409
    assert balance(pg) == Decimal('510')
    history = pg.client.get('/user/bonus_history', headers=pg.headers('client_a')).json()
    assert len(history) == 2
    assert {x['kind'] for x in history} == {'opening', 'adjustment'}
    assert all('reason' not in x and 'actor_id' not in x for x in history)
    assert pg.client.get('/user/bonus_history', headers=pg.headers('client_b')).json() == []
    assert post(pg, {**payload(pg), 'amount': '511', 'is_write_off': True}).status_code == 422
    assert balance(pg) == Decimal('510')


def test_concurrent_requests_and_rollback(pg):
    enable(pg)
    body = UpdateBonusBalanceRequest(**payload(pg))
    async def operation(request, rollback=False):
        async with pg.sessions() as session:
            await adjust_balance(session, pg.ids['admin_a'], pg.ids['client_a'], request)
            if rollback:
                await session.rollback()
            else:
                await session.commit()
    async def run():
        await asyncio.gather(operation(body), operation(body))
        await asyncio.gather(*[operation(UpdateBonusBalanceRequest(**payload(pg))) for _ in range(4)])
        await operation(UpdateBonusBalanceRequest(**payload(pg)), rollback=True)
    asyncio.run(run())
    assert balance(pg) == Decimal('550')
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(BonusTransactionDB)) == 6


def test_registration_once_and_immutable(pg):
    async def run():
        async with pg.sessions() as session, session.begin():
            user = await UserDAL(session).create_user('New', 'User', '00000000000',
                                                      'new@example.test', 'unused')
            await record_initial(session, user, welcome=True)
            return user.user_id
    user_id = asyncio.run(run())
    with pg.engine.connect() as conn:
        row = conn.execute(select(BonusTransactionDB).where(BonusTransactionDB.user_id == user_id)).one()
        assert row.kind == 'welcome' and row.amount == row.balance_after == Decimal('500')
    for statement in ['UPDATE bonus_transaction SET reason=\'edited\'', 'DELETE FROM bonus_transaction']:
        with pytest.raises(DBAPIError), pg.engine.begin() as conn:
            conn.execute(text(statement))


def test_migration_preserves_existing_balance(integration_url):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    # Start at the actual predecessor, never downgrade through protected history.
    schema = 'culta_it_' + uuid4().hex
    uid = uuid4()
    url = integration_url.set(drivername='postgresql+psycopg2')
    admin = create_engine(url, poolclass=NullPool)
    engine = create_engine(url, poolclass=NullPool,
                           connect_args={'options': f'-csearch_path={schema}'})
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / 'alembic.ini'))
    config.set_main_option('script_location', str(root / 'migrations'))
    config.set_main_option('sqlalchemy.url', url.update_query_dict(
        {'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False).replace('%', '%%'))
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        command.upgrade(config, 'b19c04e62026')
        with engine.begin() as conn:
            conn.execute(text('''INSERT INTO "user"
                (user_id, name, surname, phone, email, hashed_password, bonus_balance)
                VALUES (:uid, 'Test', 'Migration', '00000000000', 'migration@example.test',
                        'unused', 123.45)'''), {'uid': uid})
        command.upgrade(config, 'c20c04e62026')
        with engine.connect() as conn:
            assert conn.scalar(select(UserDB.bonus_balance).where(UserDB.user_id == uid)) == Decimal('123.45')
            row = conn.execute(select(BonusTransactionDB).where(BonusTransactionDB.user_id == uid)).one()
            assert row.kind == 'opening' and row.amount == row.balance_after == Decimal('123.45')
        with pytest.raises(RuntimeError, match='explicit archival procedure'):
            command.downgrade(config, 'b19c04e62026')
        command.upgrade(config, 'head')
        with engine.connect() as conn:
            assert conn.scalar(select(UserDB.bonus_balance).where(UserDB.user_id == uid)) == Decimal('123.45')
            assert conn.scalar(select(func.count()).select_from(BonusTransactionDB)) == 1
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_shared_wallet_company_switch_and_disabled_direction(pg):
    data = payload(pg)
    assert post(pg, data).status_code == 403
    enable(pg)
    assert post(pg, data).status_code == 200
    other = {**payload(pg), 'company_id': str(pg.ids['company_b']),
             'amount': '30.00', 'is_write_off': True}
    assert post(pg, other, 'admin_b').status_code == 200
    assert balance(pg) == Decimal('480.00')
    with pg.engine.connect() as conn:
        companies = set(conn.scalars(select(BonusTransactionDB.company_id).where(
            BonusTransactionDB.kind == 'adjustment')))
        assert companies == {pg.ids['company_a'], pg.ids['company_b']}
