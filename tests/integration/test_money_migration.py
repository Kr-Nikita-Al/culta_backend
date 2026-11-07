from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('pg', ['a3bf3ac3dea2'], indirect=True)
def test_legacy_rounding_nulls_and_defaults(pg):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=0.005, cost_price=123.456, cashback_perc=NULL'))
    command.upgrade(pg.migration_config, 'head')
    with pg.engine.connect() as connection:
        row = connection.execute(text('SELECT price, cost_price, cashback_perc FROM product_card LIMIT 1')).one()
        assert row == (Decimal('0.01'), Decimal('123.46'), None)
        assert connection.execute(text('SELECT bonus_balance FROM "user" LIMIT 1')).scalar_one() == Decimal('500.00')
        columns = connection.execute(text("SELECT numeric_precision, numeric_scale FROM information_schema.columns WHERE table_schema=:schema AND table_name='product_card' AND column_name='price'"), {'schema': pg.schema}).one()
        assert columns == (18, 2)


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', '-0.01', '10000000000000000'])
@pytest.mark.parametrize('pg', ['a3bf3ac3dea2'], indirect=True)
def test_invalid_legacy_data_aborts_migration(pg, value):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=CAST(:value AS double precision)'), {'value': value})
    with pytest.raises(ValueError, match='product_card.price'):
        command.upgrade(pg.migration_config, 'head')
    with pg.engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'a3bf3ac3dea2'
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE product_card SET price=0.1'))
    command.upgrade(pg.migration_config, 'head')


@pytest.mark.parametrize('statement', [
    'UPDATE product_card SET price=-1',
    "UPDATE product_card SET price='NaN'",
    'UPDATE company SET bonus_payment_perc=100.01',
    'UPDATE "user" SET bonus_balance=-1',
])
def test_database_rejects_invalid_amounts(pg, statement):
    with pytest.raises(IntegrityError), pg.engine.begin() as connection:
        connection.execute(text(statement))


def test_maximum_and_exact_arithmetic(pg):
    with pg.engine.begin() as connection:
        connection.execute(text("UPDATE product_card SET price=9999999999999999.99"))
        value = connection.execute(text('SELECT price FROM product_card LIMIT 1')).scalar_one()
        assert value == Decimal('9999999999999999.99')
        connection.execute(text('UPDATE "user" SET bonus_balance=bonus_balance+0.1+0.1+0.1-0.2'))
        assert connection.execute(text('SELECT bonus_balance FROM "user" LIMIT 1')).scalar_one() == Decimal('500.10')
