"""Journal committed image and directory moves; no automatic deletion."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a42c26e62026'
down_revision = 'a41c26e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('storage_move',
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('source_key', sa.String(1100), nullable=False),
        sa.Column('destination_key', sa.String(1100), nullable=False),
        sa.Column('copied_keys', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('image', 'directory')", name='ck_storage_move_kind'))
    op.create_index('ix_storage_move_company_created', 'storage_move', ['company_id', 'created_at'])


def downgrade():
    op.drop_table('storage_move')
