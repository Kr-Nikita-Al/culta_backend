"""Per-company employee default avatar source."""
from alembic import op
import sqlalchemy as sa

revision = 'f09b7d315c21'
down_revision = 'e06f42bc935c'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('user_role', sa.Column('avatar_default', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('user_role', 'avatar_default')
