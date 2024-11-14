"""add model user

Revision ID: ada8af0be1a2
Revises: f2d8afb7289f
Create Date: 2024-11-10 12:25:15.881584

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ada8af0be1a2'
down_revision = 'f2d8afb7289f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('surname', sa.String(), nullable=False),
    sa.Column('phone', sa.String(length=12), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('roles', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('updater_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('time_created', sa.DateTime(timezone=True), nullable=True),
    sa.Column('time_updated', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('email')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('user')
    # ### end Alembic commands ###
