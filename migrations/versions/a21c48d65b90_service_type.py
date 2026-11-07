"""Service type and immutable check mode snapshot."""
from alembic import op
import sqlalchemy as sa

revision = 'a21c48d65b90'
down_revision = 'f12a64b08c31'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('company', 'checks'):
        op.add_column(table, sa.Column('service_type', sa.String(20), nullable=False, server_default='self_service'))
        op.create_check_constraint('ck_' + ('company' if table == 'company' else 'check') + '_service_type', table,
                                   "service_type IN ('self_service', 'waiter_service')")
    # Existing checks may already group several orders; preserve that possibility.
    op.execute("UPDATE checks SET service_type='waiter_service'")


def downgrade():
    for table in ('checks', 'company'):
        op.drop_constraint('ck_' + ('company' if table == 'company' else 'check') + '_service_type', table, type_='check')
        op.drop_column(table, 'service_type')
