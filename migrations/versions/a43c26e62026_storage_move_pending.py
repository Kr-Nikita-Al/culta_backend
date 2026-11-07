"""Persist copy intent before storage; legacy journal entries are committed."""
from alembic import op
import sqlalchemy as sa

revision = 'a43c26e62026'
down_revision = 'a42c26e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('storage_move', sa.Column('status', sa.String(16), nullable=False, server_default='committed'))
    op.create_check_constraint('ck_storage_move_status', 'storage_move', "status IN ('pending', 'committed')")
    op.create_index('ix_storage_move_status_created', 'storage_move', ['status', 'created_at'])


def downgrade():
    op.drop_index('ix_storage_move_status_created', table_name='storage_move')
    op.drop_constraint('ck_storage_move_status', 'storage_move', type_='check')
    op.drop_column('storage_move', 'status')
