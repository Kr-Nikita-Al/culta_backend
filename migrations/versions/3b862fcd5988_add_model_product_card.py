"""add model product_card

Revision ID: 3b862fcd5988
Revises: 1dc716a5a5b5
Create Date: 2024-10-17 20:27:23.371548

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3b862fcd5988'
down_revision = '1dc716a5a5b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('product_card',
    sa.Column('product_card_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('title', sa.String(length=35), nullable=True),
    sa.Column('sub_title', sa.String(length=35), nullable=True),
    sa.Column('header', sa.String(length=35), nullable=True),
    sa.Column('description', sa.String(length=35), nullable=True),
    sa.Column('hint_header', sa.String(length=35), nullable=True),
    sa.Column('hint_description', sa.String(length=35), nullable=True),
    sa.Column('product_category', sa.String(length=35), nullable=True),
    sa.Column('custom_product_category', sa.String(length=35), nullable=True),
    sa.Column('product_release_type', sa.String(length=35), nullable=True),
    sa.Column('allergens_list', sa.String(length=35), nullable=True),
    sa.Column('quantity_system', sa.String(length=35), nullable=True),
    sa.Column('tags', sa.String(length=35), nullable=True),
    sa.Column('count_number', sa.Integer(), nullable=True),
    sa.Column('price_field_1', sa.Integer(), nullable=True),
    sa.Column('price_field_2', sa.Integer(), nullable=True),
    sa.Column('cost_price_field_1', sa.Integer(), nullable=True),
    sa.Column('cost_price_field_2', sa.Integer(), nullable=True),
    sa.Column('cashback_field_1', sa.Integer(), nullable=True),
    sa.Column('cashback_field_2', sa.Integer(), nullable=True),
    sa.Column('product_quantity', sa.Integer(), nullable=True),
    sa.Column('calorie_content', sa.Integer(), nullable=True),
    sa.Column('proteins', sa.Integer(), nullable=True),
    sa.Column('fats', sa.Integer(), nullable=True),
    sa.Column('carbohydrates', sa.Integer(), nullable=True),
    sa.Column('cooking_time', sa.Integer(), nullable=True),
    sa.Column('bonuses_payment', sa.Boolean(), nullable=True),
    sa.Column('single_product_type', sa.Boolean(), nullable=True),
    sa.Column('is_sharpness', sa.Boolean(), nullable=True),
    sa.Column('is_hotness', sa.Boolean(), nullable=True),
    sa.Column('company_id', postgresql.UUID(), nullable=True),
    sa.Column('company_group_id', sa.Integer(), nullable=True),
    sa.Column('product_image_id', sa.Integer(), nullable=True),
    sa.Column('icon_image_id', sa.Integer(), nullable=True),
    sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('updater_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('time_created', sa.DateTime(timezone=True), nullable=True),
    sa.Column('time_updated', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['company.company_id'], ),
    sa.PrimaryKeyConstraint('product_card_id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('product_card')
    # ### end Alembic commands ###
