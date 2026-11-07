"""Client request deduplication, table context and revocable table QR."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b19c04e62026'
down_revision = 'a18c04e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('dining_table', sa.Column('order_qr_hash', sa.String(64), nullable=True))
    for table, prefix in (('checks', 'check'), ('orders', 'order')):
        op.add_column(table, sa.Column('order_context', sa.String(16), nullable=True))
        op.add_column(table, sa.Column('table_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f'fk_{prefix}_table_scope', table, 'dining_table',
                              ['table_id', 'company_id'], ['table_id', 'company_id'], ondelete='RESTRICT')
    op.create_check_constraint('ck_check_order_context', 'checks',
        "order_context IS NULL OR (order_context = 'inside' AND table_id IS NOT NULL) OR (order_context = 'outside' AND table_id IS NULL)")
    op.add_column('orders', sa.Column('client_request_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('orders', sa.Column('client_request_hash', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_order_client_request', 'orders', ['user_id', 'client_request_id'])


def downgrade():
    op.drop_constraint('uq_order_client_request', 'orders', type_='unique')
    op.drop_column('orders', 'client_request_hash')
    op.drop_column('orders', 'client_request_id')
    op.drop_constraint('ck_check_order_context', 'checks', type_='check')
    for table, prefix in (('orders', 'order'), ('checks', 'check')):
        op.drop_constraint(f'fk_{prefix}_table_scope', table, type_='foreignkey')
        op.drop_column(table, 'table_id')
        op.drop_column(table, 'order_context')
    op.drop_column('dining_table', 'order_qr_hash')
