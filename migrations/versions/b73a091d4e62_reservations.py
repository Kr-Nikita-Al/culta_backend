"""Floor plans and whole-table bookings. Existing records are not modified."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'b73a091d4e62'
down_revision = 'a21c48d65b90'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('floor_plan',
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('company.company_id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False))
    op.create_table('dining_table',
        sa.Column('table_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('company.company_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('label', sa.String(40), nullable=False),
        sa.Column('shape', sa.String(16), nullable=False),
        sa.Column('seats', sa.Integer(), nullable=False),
        sa.Column('x', sa.Integer(), nullable=False), sa.Column('y', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=False), sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('table_id', 'company_id', name='uq_dining_table_scope'),
        sa.CheckConstraint("shape IN ('square', 'rectangle', 'circle')", name='ck_dining_table_shape'),
        sa.CheckConstraint('seats BETWEEN 1 AND 24', name='ck_dining_table_seats'),
        sa.CheckConstraint('x BETWEEN 0 AND 1000 AND y BETWEEN 0 AND 600 AND width BETWEEN 50 AND 220 AND height BETWEEN 50 AND 220', name='ck_dining_table_geometry'))
    op.create_index('ix_dining_table_company_id', 'dining_table', ['company_id'])
    op.create_table('reservation',
        sa.Column('reservation_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', UUID(as_uuid=True), nullable=False),
        sa.Column('table_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.user_id', ondelete='RESTRICT')),
        sa.Column('guest_name', sa.String(100), nullable=False), sa.Column('guest_phone', sa.String(30), nullable=False),
        sa.Column('guests', sa.Integer(), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(16), nullable=False), sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('creator_id', UUID(as_uuid=True), sa.ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('updater_id', UUID(as_uuid=True), sa.ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('time_created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_updated', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['table_id', 'company_id'], ['dining_table.table_id', 'dining_table.company_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('company_id', 'creator_id', 'request_id', name='uq_reservation_request'),
        sa.CheckConstraint('ends_at > starts_at', name='ck_reservation_interval'),
        sa.CheckConstraint('guests BETWEEN 1 AND 24', name='ck_reservation_guests'),
        sa.CheckConstraint("status IN ('confirmed', 'seated', 'completed', 'canceled')", name='ck_reservation_status'))
    op.create_index('ix_reservation_company_time', 'reservation', ['company_id', 'starts_at', 'ends_at'])


def downgrade():
    op.drop_table('reservation')
    op.drop_table('dining_table')
    op.drop_table('floor_plan')
