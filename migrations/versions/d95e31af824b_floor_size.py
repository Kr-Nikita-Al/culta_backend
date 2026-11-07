"""Persist configurable floor dimensions without moving existing objects."""
from alembic import op
import sqlalchemy as sa

revision = 'd95e31af824b'
down_revision = 'c84d20ef713a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('floor_plan', sa.Column('width', sa.Integer(), nullable=False, server_default='1000'))
    op.add_column('floor_plan', sa.Column('height', sa.Integer(), nullable=False, server_default='600'))
    op.create_check_constraint('ck_floor_plan_size', 'floor_plan', 'width BETWEEN 300 AND 4000 AND height BETWEEN 200 AND 2400')
    op.drop_constraint('ck_dining_table_geometry', 'dining_table', type_='check')
    op.create_check_constraint('ck_dining_table_geometry', 'dining_table', 'x BETWEEN 0 AND 4000 AND y BETWEEN 0 AND 2400 AND width BETWEEN 50 AND 220 AND height BETWEEN 50 AND 220')


def downgrade():
    # Refuse to discard a larger plan; no implicit truncation or repositioning.
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT count(*) FROM floor_plan WHERE width <> 1000 OR height <> 600')).scalar():
        raise RuntimeError('Restore all floor dimensions to 1000x600 before downgrading')
    op.drop_constraint('ck_dining_table_geometry', 'dining_table', type_='check')
    op.create_check_constraint('ck_dining_table_geometry', 'dining_table', 'x BETWEEN 0 AND 1000 AND y BETWEEN 0 AND 600 AND width BETWEEN 50 AND 220 AND height BETWEEN 50 AND 220')
    op.drop_constraint('ck_floor_plan_size', 'floor_plan', type_='check')
    op.drop_column('floor_plan', 'height')
    op.drop_column('floor_plan', 'width')
