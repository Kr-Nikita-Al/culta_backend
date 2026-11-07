"""Validated company-scoped loyalty and optional application sections."""
from decimal import Decimal
from typing import List
from pydantic import BaseModel, StrictBool, conint, constr, root_validator
from sqlalchemy import select, func
from db import CheckDB
from utils.money import Money, Percentage


class Rates(BaseModel):
    bonus_payment_perc: Percentage
    bonus_accrual_perc: Percentage

    @root_validator(skip_on_failure=True)
    def valid_rates(cls, values):
        if values['bonus_accrual_perc'] > values['bonus_payment_perc']:
            raise ValueError('Accrual percentage must not exceed redemption percentage')
        return values

    class Config:
        extra = 'forbid'


class LoyaltyLevel(Rates):
    name: constr(strip_whitespace=True, min_length=1, max_length=80)
    threshold: Money


class InfrastructureRequest(Rates):
    version: conint(ge=0)
    levels: List[LoyaltyLevel]
    orders_enabled: StrictBool
    reservations_enabled: StrictBool
    images_enabled: StrictBool

    @root_validator(skip_on_failure=True)
    def unique_levels(cls, values):
        levels = values['levels']
        if len({x.threshold for x in levels}) != len(levels):
            raise ValueError('Level thresholds must be unique')
        if len({x.name.casefold() for x in levels}) != len(levels):
            raise ValueError('Level names must be unique')
        return values


def infrastructure_response(company):
    return dict(version=company.infrastructure_version, levels=company.loyalty_levels,
        bonus_payment_perc=format(company.bonus_payment_perc or 0, '.2f'),
        bonus_accrual_perc=format(company.bonus_accrual_perc or 0, '.2f'),
        **{name: getattr(company, name) for name in ('orders_enabled', 'reservations_enabled', 'images_enabled')})


async def effective_rates(session, company, user_id):
    # Closed cash payments only; the currently closing (open) check does not count.
    spent = await session.scalar(select(func.coalesce(func.sum(CheckDB.paid_amount), 0)).where(
        CheckDB.company_id == company.company_id, CheckDB.user_id == user_id, CheckDB.status == 'closed'))
    payment = company.bonus_payment_perc or Decimal('0')
    accrual = company.bonus_accrual_perc or Decimal('0')
    name = None
    for level in sorted(company.loyalty_levels or [], key=lambda x: Decimal(x['threshold'])):
        if spent >= Decimal(level['threshold']):
            payment, accrual = Decimal(level['bonus_payment_perc']), Decimal(level['bonus_accrual_perc'])
            name = level['name']
    return payment, accrual, name, spent
