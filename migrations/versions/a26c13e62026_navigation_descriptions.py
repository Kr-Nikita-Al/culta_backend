"""Allow full descriptions in the menu editor."""
from alembic import op
import sqlalchemy as sa
revision = 'a26c13e62026'
down_revision = 'f25c13e62026'
branch_labels = depends_on = None

def upgrade():
    for table, column in [('product_card', 'description'), ('container', 'container_sub_title'), ('screen', 'screen_sub_title')]:
        op.alter_column(table, column, type_=sa.Text())

def downgrade():
    raise RuntimeError('Description downgrade may truncate content; manual review required')
