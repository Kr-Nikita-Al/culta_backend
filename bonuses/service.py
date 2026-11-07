"""Wallet writes share the caller's transaction; never commit here."""
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from db import UserDB, BonusTransactionDB, CompanyDB, UserRoleDB
from utils.money import MAX_MONEY


async def record_initial(session, user, *, welcome=False):
    # Caller owns a new user or a FOR UPDATE lock. Existing balances are not increased.
    existing = await session.scalar(select(BonusTransactionDB.transaction_id).where(
        BonusTransactionDB.user_id == user.user_id,
        BonusTransactionDB.kind.in_(['opening', 'welcome'])))
    if existing is None:
        session.add(BonusTransactionDB(user_id=user.user_id, request_id=uuid4(),
            kind='welcome' if welcome else 'opening', amount=user.bonus_balance,
            balance_before=Decimal('0.00'), balance_after=user.bonus_balance,
            reason='Registration bonus' if welcome else 'Existing balance'))
        await session.flush()


async def adjust_balance(session, actor_id, user_id, body):
    actor = await session.get(UserDB, actor_id)
    company = await session.get(CompanyDB, body.company_id)
    roles = (await session.scalars(select(UserRoleDB.role).where(
        UserRoleDB.user_id == actor_id, UserRoleDB.company_id == body.company_id,
        UserRoleDB.is_active.is_(True)))).all()
    if (not actor or not actor.is_active or actor_id == user_id or not company
            or not company.is_active or not set(roles) & {'PORTAL_ROLE_OWNER', 'PORTAL_ROLE_ADMIN'}):
        raise HTTPException(403, 'Only an active company owner or administrator can adjust bonuses')
    user = await session.scalar(select(UserDB).where(UserDB.user_id == user_id)
                                .with_for_update().execution_options(populate_existing=True))
    if not user or not user.is_active:
        raise HTTPException(404, 'Active user not found')
    amount = -body.amount if body.is_write_off else body.amount
    previous = await session.scalar(select(BonusTransactionDB).where(
        BonusTransactionDB.user_id == user_id, BonusTransactionDB.request_id == body.request_id))
    if previous:
        if (previous.kind, previous.company_id, previous.actor_id, previous.amount, previous.reason) != (
                'adjustment', body.company_id, actor_id, amount, body.reason):
            raise HTTPException(409, 'Request ID already used for another bonus operation')
        return previous
    percentage = company.bonus_payment_perc if body.is_write_off else company.bonus_accrual_perc
    if not percentage or percentage <= 0:
        raise HTTPException(403, 'This bonus operation is disabled by the company')
    after = user.bonus_balance + amount
    if not Decimal('0') <= after <= MAX_MONEY:
        raise HTTPException(422, 'Bonus balance outside the supported range')
    await record_initial(session, user)
    entry = BonusTransactionDB(user_id=user_id, company_id=body.company_id,
        actor_id=actor_id, request_id=body.request_id, kind='adjustment', amount=amount,
        balance_before=user.bonus_balance, balance_after=after, reason=body.reason)
    session.add(entry)
    user.bonus_balance = after
    await session.flush()
    return entry
