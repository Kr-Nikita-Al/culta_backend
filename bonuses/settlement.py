"""Exact check settlement. Caller holds the wallet and check locks."""
from decimal import Decimal, ROUND_DOWN
from uuid import uuid4
from fastapi import HTTPException
from db import BonusTransactionDB
from bonuses.service import record_initial
from utils.money import CENT, MAX_MONEY
from company.infrastructure import effective_rates


def percentage_amount(amount, percentage):
    return (amount * (percentage or Decimal('0')) / Decimal('100')).quantize(CENT, rounding=ROUND_DOWN)


def redemption_limit(total, balance, percentage):
    return min(balance, percentage_amount(total, percentage))


async def settle(session, check, user, company, total, paid, spent, actor):
    payment_rate, accrual_rate, level, cumulative = await effective_rates(session, company, user.user_id)
    if accrual_rate > payment_rate:
        raise HTTPException(409, 'Invalid company bonus settings')
    if spent > redemption_limit(total, user.bonus_balance, payment_rate):
        raise HTTPException(409, 'Requested bonuses exceed the balance or company limit')
    if paid + spent != total:
        raise HTTPException(409, 'Payment plus bonuses must equal the current check total')
    earned = percentage_amount(paid, accrual_rate)
    if user.bonus_balance - spent + earned > MAX_MONEY:
        raise HTTPException(422, 'Bonus balance exceeds the supported amount')
    if spent or earned:
        if not user.is_active:
            raise HTTPException(409, 'Bonus wallet is inactive')
        await record_initial(session, user)
        for kind, amount in [('redemption', -spent), ('accrual', earned)]:
            if not amount:
                continue
            session.add(BonusTransactionDB(user_id=user.user_id, company_id=check.company_id,
                check_id=check.check_id, actor_id=actor, request_id=uuid4(), kind=kind,
                amount=amount, balance_before=user.bonus_balance,
                balance_after=user.bonus_balance + amount, reason='Check settlement'))
            user.bonus_balance += amount
    check.bonus_spent = spent
    check.bonus_earned = earned
    check.bonus_payment_perc = payment_rate
    check.bonus_accrual_perc = accrual_rate
    check.loyalty_level_name = level
