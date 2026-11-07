"""Persist menu canvas coordinates without changing existing navigation."""
from alembic import op
import sqlalchemy as sa

revision = 'c28c15e62026'
down_revision = 'b27c14e62026'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('screen', sa.Column('editor_version', sa.Integer(), nullable=False, server_default='0'))
    for table in ('container', 'item'):
        op.add_column(table, sa.Column('layout_x', sa.Integer(), nullable=True))
        op.add_column(table, sa.Column('layout_y', sa.Integer(), nullable=True))

def downgrade():
    for table in ('item', 'container'):
        op.drop_column(table, 'layout_y')
        op.drop_column(table, 'layout_x')
    op.drop_column('screen', 'editor_version')
