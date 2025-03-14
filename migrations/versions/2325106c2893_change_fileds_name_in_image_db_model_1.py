"""change fileds name in image db_model 1

Revision ID: 2325106c2893
Revises: 16290a9faa30
Create Date: 2025-02-07 11:29:15.881672

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2325106c2893'
down_revision = '16290a9faa30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('image', sa.Column('file_name', sa.String(length=100), nullable=True))
    op.drop_column('image', 'title')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('image', sa.Column('title', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.drop_column('image', 'file_name')
    # ### end Alembic commands ###
