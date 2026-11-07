import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from order.order_product_association.snapshot import capture_snapshot, line_total
from order.order_product_association.model_dal import OrderProductAssociationDal


@pytest.mark.parametrize('cost', [None, '-0.01', 'NaN', 'Infinity', '0.001'])
def test_invalid_cost_cannot_be_captured(cost):
    product = SimpleNamespace(title='Coffee', price=Decimal('1.00'), cost_price=cost)
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one_or_none=lambda: product)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(capture_snapshot(session, uuid4(), uuid4(), 1))
    assert error.value.status_code == 422


def test_fractional_line_total_and_limits():
    assert line_total(Decimal('0.10'), 3) == Decimal('0.30')
    assert line_total(Decimal('0.10'), 0) == Decimal('0.00')
    with pytest.raises(HTTPException):
        line_total(Decimal('9999999999999999.99'), 2)


def test_update_overflow_does_not_write():
    position = SimpleNamespace(unit_price=Decimal('9999999999999999.99'))
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: position)))
    with pytest.raises(HTTPException):
        asyncio.run(OrderProductAssociationDal(session).update_order_product(uuid4(), uuid4(), quantity=2))
    assert session.execute.await_count == 1
