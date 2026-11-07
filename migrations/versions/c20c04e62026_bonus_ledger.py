"""Shared wallet ledger; preserve existing balances, never regrant welcome points."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'c20c04e62026'
down_revision = 'b19c04e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('bonus_transaction',
        sa.Column('transaction_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.user_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('company.company_id', ondelete='RESTRICT')),
        sa.Column('check_id', UUID(as_uuid=True)),
        sa.Column('actor_id', UUID(as_uuid=True), sa.ForeignKey('user.user_id', ondelete='RESTRICT')),
        sa.Column('request_id', UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('balance_before', sa.Numeric(18, 2), nullable=False),
        sa.Column('balance_after', sa.Numeric(18, 2), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['check_id', 'company_id', 'user_id'], ['checks.check_id', 'checks.company_id', 'checks.user_id'], ondelete='RESTRICT'),
        sa.CheckConstraint("kind IN ('opening', 'welcome', 'accrual', 'redemption', 'refund', 'adjustment')", name='ck_bonus_kind'),
        sa.CheckConstraint('balance_after = balance_before + amount', name='ck_bonus_arithmetic'),
        sa.CheckConstraint('balance_before BETWEEN 0 AND 9999999999999999.99 AND balance_after BETWEEN 0 AND 9999999999999999.99', name='ck_bonus_balances'),
        sa.CheckConstraint("(kind IN ('opening', 'welcome') AND company_id IS NULL AND check_id IS NULL AND balance_before = 0) OR (kind = 'adjustment' AND company_id IS NOT NULL AND actor_id IS NOT NULL AND amount <> 0) OR (kind IN ('accrual', 'refund') AND check_id IS NOT NULL AND company_id IS NOT NULL AND amount > 0) OR (kind = 'redemption' AND check_id IS NOT NULL AND company_id IS NOT NULL AND amount < 0)", name='ck_bonus_scope'),
        sa.CheckConstraint("kind <> 'welcome' OR amount = 500", name='ck_bonus_welcome'),
    )
    op.create_index('ix_bonus_transaction_user_id', 'bonus_transaction', ['user_id'])
    op.create_index('uq_bonus_request', 'bonus_transaction', ['user_id', 'request_id'], unique=True)
    op.create_index('uq_bonus_initial', 'bonus_transaction', ['user_id'], unique=True,
                    postgresql_where=sa.text("kind IN ('opening', 'welcome')"))
    # Exclusive user-table lock avoids balance changes during the opening snapshot.
    op.execute('LOCK TABLE "user" IN SHARE ROW EXCLUSIVE MODE')
    op.execute("""INSERT INTO bonus_transaction
        (transaction_id, user_id, request_id, kind, amount, balance_before, balance_after, reason)
        SELECT user_id, user_id, user_id, 'opening', COALESCE(bonus_balance, 0), 0,
               COALESCE(bonus_balance, 0), 'Existing balance at ledger migration' FROM "user"
        """)
    op.execute("""CREATE FUNCTION reject_bonus_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Bonus ledger is append-only'; END;
        $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER bonus_history_immutable BEFORE UPDATE OR DELETE ON bonus_transaction '
               'FOR EACH ROW EXECUTE FUNCTION reject_bonus_history_change()')


def downgrade():
    # Never silently delete financial history via an application downgrade.
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM bonus_transaction')):
        raise RuntimeError('Bonus ledger downgrade requires an explicit archival procedure')
    op.drop_table('bonus_transaction')
    op.execute('DROP FUNCTION reject_bonus_history_change()')
