"""Company loyalty levels and optional sections; preserve historical checks."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = 'e22c12e62026'
down_revision = 'd21c04e62026'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM company WHERE bonus_accrual_perc > bonus_payment_perc')):
        raise RuntimeError('Existing companies have accrual above redemption; review settings before migration')
    op.create_check_constraint('ck_company_bonus_ratio', 'company', 'bonus_accrual_perc <= bonus_payment_perc')
    op.add_column('company', sa.Column('loyalty_levels', JSONB, nullable=False, server_default='[]'))
    op.add_column('company', sa.Column('infrastructure_version', sa.Integer, nullable=False, server_default='0'))
    for name in ('orders_enabled', 'reservations_enabled', 'images_enabled'):
        op.add_column('company', sa.Column(name, sa.Boolean, nullable=False, server_default='true'))
    op.add_column('checks', sa.Column('loyalty_level_name', sa.String(80), nullable=True))


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM company WHERE loyalty_levels <> '[]'::jsonb")):
        raise RuntimeError('Archive loyalty settings before downgrade')
    op.drop_column('checks', 'loyalty_level_name')
    for name in ('loyalty_levels', 'infrastructure_version', 'orders_enabled', 'reservations_enabled', 'images_enabled'):
        op.drop_column('company', name)
    op.drop_constraint('ck_company_bonus_ratio', 'company', type_='check')
