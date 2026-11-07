"""Add order status audit trail without inventing historical events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e06f42bc935c'
down_revision = 'd95e31af824b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('order_status_history',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('orders.order_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('old_status', sa.String(20), nullable=True),
        sa.Column('new_status', sa.String(20), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('clock_timestamp()')),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.CheckConstraint("old_status IS NULL OR old_status IN ('created','processing','completed','canceled','closed')", name='ck_history_old_status'),
        sa.CheckConstraint("new_status IN ('created','processing','completed','canceled','closed')", name='ck_history_new_status'),
        sa.CheckConstraint('old_status IS NULL OR old_status <> new_status', name='ck_history_transition'))
    op.create_index('ix_history_order_time', 'order_status_history', ['order_id', 'changed_at', 'event_id'])


def downgrade():
    op.drop_table('order_status_history')
