"""Durable directory deletion outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a44c28e62026'
down_revision = 'a43c26e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('storage_delete',
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prefix', sa.String(1100), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('keys', postgresql.JSONB(), nullable=False),
        sa.Column('image_ids', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'done')", name='ck_storage_delete_status'))
    op.create_index('ix_storage_delete_company_status', 'storage_delete', ['company_id', 'status'])


def downgrade():
    op.drop_table('storage_delete')
