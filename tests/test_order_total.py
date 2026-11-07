import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from order.order_product_association.model_dal import OrderProductAssociationDal


def total(rows):
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))
    return asyncio.run(OrderProductAssociationDal(session).calculate_order_total(uuid4()))


def test_empty_and_fractional_totals():
    assert total([]) == Decimal('0.00')
    assert total([(Decimal('0.10'), 3), (Decimal('0.20'), 2)]) == Decimal('0.70')


@pytest.mark.parametrize('rows,code', [
    ([(None, 1)], 409), ([(None, 0)], 409),
    ([(Decimal('6000000000000000'), 1)] * 2, 422),
])
def test_unknown_prices_and_overflow(rows, code):
    with pytest.raises(HTTPException) as error:
        total(rows)
    assert error.value.status_code == code
