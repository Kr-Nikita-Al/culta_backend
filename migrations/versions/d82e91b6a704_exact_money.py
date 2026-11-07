"""Use exact monetary amounts and bounded percentages.

Revision ID: d82e91b6a704
Revises: a3bf3ac3dea2
"""
from alembic import op
import sqlalchemy as sa

revision = 'd82e91b6a704'
down_revision = 'a3bf3ac3dea2'
branch_labels = None
depends_on = None

FIELDS = (
    ('product_card', 'price', 18),
    ('product_card', 'cost_price', 18),
    ('product_card', 'cashback_perc', 5),
    ('orders', 'price', 18),
    ('orders', 'bonus_transaction', 18),
    ('user', 'bonus_balance', 18),
    ('company', 'bonus_payment_perc', 5),
    ('company', 'bonus_accrual_perc', 5),
)


def constraint_name(table, column):
    return f'ck_{"order" if table == "orders" else table}_{column}_range'


def upgrade():
    connection = op.get_bind()
    # Lock before validation so concurrent writes cannot bypass the preflight.
    connection.execute(sa.text('LOCK TABLE "company", "orders", "product_card", "user" IN ACCESS EXCLUSIVE MODE'))
    for table, column, precision in FIELDS:
        maximum = '100' if precision == 5 else '9999999999999999.99'
        invalid = connection.execute(sa.text(f'''
            SELECT count(*) FROM "{table}" WHERE "{column}" IS NOT NULL AND
            CASE WHEN "{column}"::text IN ('NaN', 'Infinity', '-Infinity') THEN true
            ELSE "{column}" < 0 OR "{column}"::text::numeric > {maximum}
                 OR round("{column}"::text::numeric, 2) > {maximum} END
        ''')).scalar_one()
        if invalid:
            raise ValueError(f'Cannot migrate {table}.{column}: {invalid} invalid amount(s); repair before retrying')
    for table, column, precision in FIELDS:
        maximum = '100' if precision == 5 else '9999999999999999.99'
        op.alter_column(table, column, existing_type=sa.Float(), type_=sa.Numeric(precision, 2),
                        postgresql_using=f'round("{column}"::text::numeric, 2)')
        op.create_check_constraint(constraint_name(table, column), table,
                                   f'"{column}" >= 0 AND "{column}" <= {maximum}')


def downgrade():
    # Lossy: binary floating point cannot retain all decimal amounts exactly.
    for table, column, precision in reversed(FIELDS):
        op.drop_constraint(constraint_name(table, column), table, type_='check')
        op.alter_column(table, column, existing_type=sa.Numeric(precision, 2), type_=sa.Float(),
                        postgresql_using=f'"{column}"::double precision')
