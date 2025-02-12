"""add model company

Revision ID: 5a66b1cb7fbf
Revises: 
Create Date: 2024-10-17 19:26:44.234207

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5a66b1cb7fbf'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('company',
    sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('company_name', sa.String(length=20), nullable=False),
    sa.Column('address', sa.String(length=50), nullable=False),
    sa.Column('phone', sa.String(length=12), nullable=False),
    sa.Column('email', sa.String(length=35), nullable=False),
    sa.Column('order_number', sa.Integer(), nullable=True),
    sa.Column('main_screen_id', sa.Integer(), nullable=True),
    sa.Column('group_id', sa.Integer(), nullable=True),
    sa.Column('company_image', sa.String(), nullable=True),
    sa.Column('company_icon', sa.String(), nullable=True),
    sa.Column('age_limit', sa.Boolean(), nullable=True),
    sa.Column('work_state', sa.Boolean(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('updater_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('time_created', sa.DateTime(timezone=True), nullable=True),
    sa.Column('time_updated', sa.DateTime(timezone=True), nullable=True),
    sa.Column('start_time', sa.Time(), nullable=True),
    sa.Column('over_time', sa.Time(), nullable=True),
    sa.PrimaryKeyConstraint('company_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('company')
    # ### end Alembic commands ###
