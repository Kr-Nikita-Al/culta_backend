"""Guest checks without synthetic accounts; null-safe order ownership."""
from alembic import op
import sqlalchemy as sa

revision = 'a38c21e62026'
down_revision = 'a37c20e62026'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('checks', 'user_id', nullable=True)
    op.alter_column('orders', 'user_id', nullable=True)
    op.add_column('checks', sa.Column('guest_name', sa.String(100), nullable=True))
    op.create_check_constraint('ck_guest_no_bonuses', 'checks', 'user_id IS NOT NULL OR (bonus_spent = 0 AND bonus_earned = 0)')
    op.create_unique_constraint('uq_check_company', 'checks', ['check_id', 'company_id'])
    op.create_foreign_key('fk_order_check_company', 'orders', 'checks',
                          ['check_id', 'company_id'], ['check_id', 'company_id'], ondelete='RESTRICT')
    op.execute('ALTER TABLE orders ALTER CONSTRAINT fk_order_check_scope DEFERRABLE INITIALLY DEFERRED')
    # MATCH SIMPLE on the old FK ignores NULL clients. Enforce equality including NULL,
    # deferred so linking a check and all its orders is one atomic transaction.
    op.execute('''CREATE FUNCTION validate_guest_check_owner() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS (SELECT 1 FROM orders o JOIN checks c ON c.check_id = o.check_id
                 WHERE o.check_id = NEW.check_id AND o.user_id IS DISTINCT FROM c.user_id) THEN
        RAISE EXCEPTION 'Order/check client mismatch' USING ERRCODE = '23503';
      END IF;
      RETURN NULL;
    END $$''')
    for table in ('orders', 'checks'):
        op.execute(f'''CREATE CONSTRAINT TRIGGER guest_check_owner_{table}
            AFTER INSERT OR UPDATE ON {table} DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION validate_guest_check_owner()''')


def downgrade():
    # Never erase guest financial history to make a downgrade fit NOT NULL.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM checks WHERE user_id IS NULL) OR EXISTS (SELECT 1 FROM orders WHERE user_id IS NULL) THEN RAISE EXCEPTION 'Guest records exist; downgrade refused'; END IF; END $$")
    for table in ('orders', 'checks'):
        op.execute(f'DROP TRIGGER guest_check_owner_{table} ON {table}')
    op.execute('DROP FUNCTION validate_guest_check_owner()')
    op.drop_constraint('fk_order_check_company', 'orders', type_='foreignkey')
    op.drop_constraint('uq_check_company', 'checks', type_='unique')
    op.execute('ALTER TABLE orders ALTER CONSTRAINT fk_order_check_scope NOT DEFERRABLE')
    op.drop_column('checks', 'guest_name')
    op.drop_constraint('ck_guest_no_bonuses', 'checks', type_='check')
    op.alter_column('checks', 'user_id', nullable=False)
    op.alter_column('orders', 'user_id', nullable=False)
