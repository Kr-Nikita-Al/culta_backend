"""fix field screen_order_number

Revision ID: 71ba95b6d216
Revises: bab353f34589
Create Date: 2025-02-01 13:20:35.216958

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71ba95b6d216'
down_revision = 'bab353f34589'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('container', sa.Column('container_order_number', sa.Integer(), nullable=False))
    op.drop_constraint('container_container_order_key', 'container', type_='unique')
    op.create_unique_constraint(None, 'container', ['container_order_number'])
    op.drop_column('container', 'container_order')
    op.add_column('screen', sa.Column('screen_order_number', sa.Integer(), nullable=True))
    op.create_unique_constraint(None, 'screen', ['screen_order_number'])
    op.drop_column('screen', 'screen_count_number')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('screen', sa.Column('screen_count_number', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'screen', type_='unique')
    op.drop_column('screen', 'screen_order_number')
    op.add_column('container', sa.Column('container_order', sa.INTEGER(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'container', type_='unique')
    op.create_unique_constraint('container_container_order_key', 'container', ['container_order'])
    op.drop_column('container', 'container_order_number')
    # ### end Alembic commands ###
