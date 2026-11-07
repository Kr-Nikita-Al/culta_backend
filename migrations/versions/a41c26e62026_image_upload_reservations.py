"""Track new presigned image uploads without classifying legacy images."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a41c26e62026'
down_revision = 'a40c23e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('image_upload_reservation',
        sa.Column('image_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('object_key', sa.String(1100), nullable=False),
        sa.Column('cleanup_after', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['image_id', 'company_id'],
            ['image.image_id', 'image.company_id'], ondelete='CASCADE'))
    op.create_index('ix_image_upload_reservation_cleanup', 'image_upload_reservation', ['company_id', 'cleanup_after'])


def downgrade():
    op.drop_table('image_upload_reservation')
