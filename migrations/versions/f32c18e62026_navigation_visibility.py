"""Navigation publication flags."""
from alembic import op
import sqlalchemy as sa
revision = 'f32c18e62026'
down_revision = 'e31c18e62026'
branch_labels = None
depends_on = None

def upgrade():
    for table in ('screen', 'container', 'item'):
        for name in ('is_active', 'is_visible'):
            op.add_column(table, sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()))

def downgrade():
    for table in ('item', 'container', 'screen'):
        for name in ('is_visible', 'is_active'):
            op.drop_column(table, name)
