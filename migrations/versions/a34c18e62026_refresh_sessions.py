"""Refresh sessions with bounded rotation history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision = 'a34c18e62026'
down_revision = 'f32c18e62026'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('refresh_session',
        sa.Column('session_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.user_id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('credential_hash', sa.String(64), nullable=False),
        sa.Column('used_hashes', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False))

def downgrade():
    op.drop_table('refresh_session')
