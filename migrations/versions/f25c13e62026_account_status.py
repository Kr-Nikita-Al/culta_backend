"""Global account status and single-use email confirmation."""
from alembic import op
import sqlalchemy as sa

revision = 'f25c13e62026'
down_revision = 'e22c12e62026'
branch_labels = depends_on = None


def upgrade():
    op.add_column('user', sa.Column('account_status', sa.String(16), nullable=False, server_default='pending'))
    op.add_column('user', sa.Column('email_code_hash', sa.String(64)))
    op.add_column('user', sa.Column('email_code_expires', sa.DateTime(timezone=True)))
    op.add_column('user', sa.Column('email_code_sent_at', sa.DateTime(timezone=True)))
    op.add_column('user', sa.Column('email_code_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.execute("""UPDATE "user" u SET account_status = CASE WHEN NOT coalesce(is_active,false) THEN 'deleted'
        WHEN EXISTS (SELECT 1 FROM oauth_accounts a WHERE a.user_id=u.user_id AND a.provider::text='YANDEX') THEN 'confirmed'
        ELSE 'pending' END""")
    op.create_check_constraint('ck_user_account_status', 'user', "account_status IN ('pending','confirmed','blocked','deleted')")


def downgrade():
    raise RuntimeError('Account status downgrade would restore access to restricted accounts; manual review required')
