"""Allow provider accounts without an email address."""
from alembic import op
import sqlalchemy as sa
revision = 'a37c20e62026'
down_revision = 'a34c18e62026'
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column('user', 'email', existing_type=sa.String(), nullable=True)

def downgrade():
    # Refuse if email-less accounts exist; never invent addresses or delete users.
    op.alter_column('user', 'email', existing_type=sa.String(), nullable=False)
