from alembic import op
import sqlalchemy as sa
revision='b27c14e62026'
down_revision='a26c13e62026'
branch_labels=depends_on=None
def upgrade():
    op.add_column('user',sa.Column('password_code_hash',sa.String(64)))
    op.add_column('user',sa.Column('password_code_expires',sa.DateTime(timezone=True)))
    op.add_column('user',sa.Column('password_code_sent_at',sa.DateTime(timezone=True)))
    op.add_column('user',sa.Column('password_code_attempts',sa.Integer(),nullable=False,server_default='0'))
def downgrade():
    for column in ('password_code_hash','password_code_expires','password_code_sent_at','password_code_attempts'):
        op.drop_column('user',column)
