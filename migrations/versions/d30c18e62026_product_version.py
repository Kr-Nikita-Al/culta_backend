"""Optimistic concurrency token for product cards."""
from alembic import op
import sqlalchemy as sa

revision = 'd30c18e62026'
down_revision = 'c28c15e62026'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('product_card', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))

def downgrade():
    op.drop_column('product_card', 'version')
