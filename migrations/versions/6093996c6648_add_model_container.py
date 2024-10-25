"""add model container

Revision ID: 6093996c6648
Revises: ee6f61b63e02
Create Date: 2024-10-25 21:47:17.576358

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6093996c6648'
down_revision = 'ee6f61b63e02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('container',
    sa.Column('container_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('container_title', sa.String(length=100), nullable=True),
    sa.Column('container_sub_title', sa.String(length=100), nullable=True),
    sa.Column('container_type', sa.String(length=35), nullable=True),
    sa.Column('container_order', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('container_id')
    )
    op.add_column('item', sa.Column('container_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key(None, 'item', 'container', ['container_id'], ['container_id'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'item', type_='foreignkey')
    op.drop_column('item', 'container_id')
    op.drop_table('container')
    # ### end Alembic commands ###