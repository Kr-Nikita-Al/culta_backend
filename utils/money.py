"""Exact amounts: accept JSON numbers/strings, emit fixed-point strings."""
from decimal import Decimal

from pydantic import ConstrainedDecimal

MAX_MONEY = Decimal('9999999999999999.99')
CENT = Decimal('0.01')


class Money(ConstrainedDecimal):
    ge = Decimal('0')
    le = MAX_MONEY
    max_digits = 18
    decimal_places = 2


class Percentage(Money):
    le = Decimal('100')
    max_digits = 5


class MoneyResponse(Money):
    @classmethod
    def __modify_schema__(cls, schema):
        schema.clear()
        schema.update(type='string', pattern=r'^\d+\.\d{2}$', example='250.50')


class PercentageResponse(Percentage):
    @classmethod
    def __modify_schema__(cls, schema):
        schema.clear()
        schema.update(type='string', pattern=r'^\d+\.\d{2}$', example='5.00')


def encode_decimal(value: Decimal) -> str:
    return format(value, '.2f')
