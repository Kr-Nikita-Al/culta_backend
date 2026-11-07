"""Add financial checks without changing existing order semantics or history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f12a64b08c31'
down_revision = 'e49e37c102a8'
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table('checks',
        sa.Column('check_id', uuid, primary_key=True),
        sa.Column('company_id', uuid, sa.ForeignKey('company.company_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('user_id', uuid, sa.ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='open'),
        sa.Column('total_amount', sa.Numeric(18, 2), nullable=True),
        sa.Column('paid_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creator_id', uuid, sa.ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('updater_id', uuid, sa.ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('time_created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_updated', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('check_id', 'company_id', 'user_id', name='uq_check_scope'),
        sa.CheckConstraint("status IN ('open', 'closed', 'canceled')", name='ck_check_status'),
        sa.CheckConstraint('total_amount IS NULL OR total_amount BETWEEN 0 AND 9999999999999999.99', name='ck_check_total_range'),
        sa.CheckConstraint('paid_amount BETWEEN 0 AND 9999999999999999.99', name='ck_check_paid_range'),
        sa.CheckConstraint('total_amount IS NULL OR paid_amount <= total_amount', name='ck_check_paid_limit'),
        sa.CheckConstraint("(status = 'closed' AND closed_at IS NOT NULL AND total_amount IS NOT NULL) OR "
                           "(status <> 'closed' AND closed_at IS NULL)", name='ck_check_closed_state'),
    )
    op.create_index('ix_checks_company_id', 'checks', ['company_id'])
    op.add_column('orders', sa.Column('check_id', uuid, nullable=True))
    op.create_index('ix_orders_check_id', 'orders', ['check_id'])
    op.create_foreign_key('fk_order_check_scope', 'orders', 'checks',
                          ['check_id', 'company_id', 'user_id'], ['check_id', 'company_id', 'user_id'],
                          ondelete='RESTRICT')


def downgrade():
    # Removing checks discards financial history: back up before downgrading.
    op.drop_constraint('fk_order_check_scope', 'orders', type_='foreignkey')
    op.drop_index('ix_orders_check_id', table_name='orders')
    op.drop_column('orders', 'check_id')
    op.drop_index('ix_checks_company_id', table_name='checks')
    op.drop_table('checks')
