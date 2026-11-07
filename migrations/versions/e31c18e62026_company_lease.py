"""Temporary company editor leases."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='e31c18e62026'
down_revision='d30c18e62026'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('company',sa.Column('edit_lease_token',UUID(as_uuid=True),nullable=True))
    op.add_column('company',sa.Column('edit_lease_user_id',UUID(as_uuid=True),nullable=True))
    op.add_column('company',sa.Column('edit_lease_expires_at',sa.DateTime(timezone=True),nullable=True))
def downgrade():
    for name in ('edit_lease_expires_at','edit_lease_user_id','edit_lease_token'):
        op.drop_column('company',name)
