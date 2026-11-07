"""Shared authentication rate-limit counters."""
from alembic import op
import sqlalchemy as sa

revision = 'a40c23e62026'
down_revision = 'a39c21e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_rate_limit',
        sa.Column('bucket_key', sa.String(64), primary_key=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_auth_rate_limit_expires', 'auth_rate_limit', ['expires_at'])


def downgrade():
    op.drop_table('auth_rate_limit')
