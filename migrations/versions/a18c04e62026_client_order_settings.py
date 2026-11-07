"""Separate inside/outside client order permissions."""
from alembic import op
import sqlalchemy as sa

revision = 'a18c04e62026'
down_revision = 'f09b7d315c21'
branch_labels = None
depends_on = None


def upgrade():
    for name in ('allow_client_orders_inside', 'allow_client_orders_outside'):
        op.add_column('company', sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute('UPDATE company SET allow_client_orders_inside = COALESCE(is_can_client_create_order, false), '
               'allow_client_orders_outside = COALESCE(is_can_client_create_order, false), '
               'is_can_client_create_order = COALESCE(is_can_client_create_order, false)')


def downgrade():
    op.execute('UPDATE company SET is_can_client_create_order = allow_client_orders_inside OR allow_client_orders_outside')
    op.drop_column('company', 'allow_client_orders_outside')
    op.drop_column('company', 'allow_client_orders_inside')
