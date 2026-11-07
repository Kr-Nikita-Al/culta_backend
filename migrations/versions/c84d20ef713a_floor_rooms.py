"""Add named room boundaries to versioned floor plans."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'c84d20ef713a'
down_revision = 'b73a091d4e62'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('floor_plan', sa.Column('rooms', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade():
    op.drop_column('floor_plan', 'rooms')
