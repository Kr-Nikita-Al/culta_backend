"""Check-level bonus settlement, without processing historical closed checks."""
from alembic import op
import sqlalchemy as sa

revision = 'd21c04e62026'
down_revision = 'c20c04e62026'
branch_labels = None
depends_on = None


def upgrade():
    for name in ('bonus_spent', 'bonus_earned'):
        op.add_column('checks', sa.Column(name, sa.Numeric(18, 2), nullable=False, server_default='0'))
        op.create_check_constraint('ck_check_' + name, 'checks', f'{name} BETWEEN 0 AND 9999999999999999.99')
    for name in ('bonus_payment_perc', 'bonus_accrual_perc'):
        op.add_column('checks', sa.Column(name, sa.Numeric(5, 2), nullable=True))
        op.create_check_constraint('ck_check_' + name, 'checks', f'{name} BETWEEN 0 AND 100')
    op.create_index('uq_bonus_check_settlement', 'bonus_transaction', ['check_id', 'kind'], unique=True,
                    postgresql_where=sa.text("kind IN ('accrual', 'redemption')"))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM checks WHERE bonus_spent <> 0 OR bonus_earned <> 0')):
        raise RuntimeError('Cannot remove settled bonus history')
    op.drop_index('uq_bonus_check_settlement', table_name='bonus_transaction')
    for name in ('bonus_spent', 'bonus_earned', 'bonus_payment_perc', 'bonus_accrual_perc'):
        op.drop_constraint('ck_check_' + name, 'checks', type_='check')
        op.drop_column('checks', name)
