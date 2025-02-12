"""update fields model product_card

Revision ID: 66bf6dc366bd
Revises: 3b862fcd5988
Create Date: 2024-10-21 13:05:35.766968

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '66bf6dc366bd'
down_revision = '3b862fcd5988'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('product_card', 'company_id',
               existing_type=postgresql.UUID(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('product_card', 'company_id',
               existing_type=postgresql.UUID(),
               nullable=True)
    # ### end Alembic commands ###
