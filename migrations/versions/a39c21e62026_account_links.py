"""Explicit linking flows and persistent symmetric duplicate dismissals."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
revision='a39c21e62026'
down_revision='a38c21e62026'
branch_labels=None
depends_on=None


def upgrade():
    # Refuse conflicting legacy identities instead of choosing an owner silently.
    op.create_unique_constraint('uq_oauth_provider_identity','oauth_accounts',['provider','provider_user_id'])
    op.create_table('account_link_flow',
        sa.Column('flow_id',UUID(as_uuid=True),primary_key=True),
        sa.Column('user_id',UUID(as_uuid=True),sa.ForeignKey('user.user_id'),nullable=False),
        sa.Column('provider',sa.String(20),nullable=False),
        sa.Column('target_user_id',UUID(as_uuid=True),sa.ForeignKey('user.user_id'),nullable=True),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('consumed',sa.Boolean(),nullable=False))
    op.create_table('account_suggestion',
        sa.Column('suggestion_id',UUID(as_uuid=True),primary_key=True),
        sa.Column('left_id',UUID(as_uuid=True),sa.ForeignKey('user.user_id'),nullable=False),
        sa.Column('right_id',UUID(as_uuid=True),sa.ForeignKey('user.user_id'),nullable=False),
        sa.Column('status',sa.String(16),nullable=False),
        sa.Column('changed_by',UUID(as_uuid=True),sa.ForeignKey('user.user_id')),
        sa.Column('verification_attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('verify_after',sa.DateTime(timezone=True)),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('left_id','right_id',name='uq_account_suggestion_pair'),
        sa.CheckConstraint('left_id < right_id',name='ck_account_suggestion_order'),
        sa.CheckConstraint("status IN ('pending','dismissed','verified')",name='ck_account_suggestion_status'))


def downgrade():
    raise RuntimeError('Account-link audit and dismissed suggestions must be preserved; manual rollback required')
