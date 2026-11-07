"""Persist order position snapshots without fabricating legacy history."""
from alembic import op
import sqlalchemy as sa

revision = 'e49e37c102a8'
down_revision = 'd82e91b6a704'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('order_product_association', sa.Column('product_title', sa.String(35), nullable=True))
    for field in ('unit_price', 'unit_cost_price', 'line_total'):
        op.add_column('order_product_association', sa.Column(field, sa.Numeric(18, 2), nullable=True))
    # Existing rows stay NULL: today's catalog is not proof of the sale price.
    op.create_check_constraint('ck_order_position_snapshot', 'order_product_association',
        '(product_title IS NULL AND unit_price IS NULL AND unit_cost_price IS NULL AND line_total IS NULL) OR '
        '(product_title IS NOT NULL AND unit_price IS NOT NULL AND unit_cost_price IS NOT NULL AND line_total IS NOT NULL '
        'AND quantity IS NOT NULL AND quantity >= 0 '
        'AND unit_price BETWEEN 0 AND 9999999999999999.99 '
        'AND unit_cost_price BETWEEN 0 AND 9999999999999999.99 '
        'AND line_total BETWEEN 0 AND 9999999999999999.99 AND line_total = unit_price * quantity)')


def downgrade():
    # This loses captured history; back up before downgrading.
    op.drop_constraint('ck_order_position_snapshot', 'order_product_association', type_='check')
    for field in ('line_total', 'unit_cost_price', 'unit_price', 'product_title'):
        op.drop_column('order_product_association', field)
