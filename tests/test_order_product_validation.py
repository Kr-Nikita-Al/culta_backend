import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from order.interface_request.create_order_request import CreateOrderProductItem
from order.order_product_association.interface_request import CreateOrderProductRequest
from order.order_product_association.snapshot import capture_snapshot
from utils.order_quantity import MAX_ORDER_QUANTITY


@pytest.mark.parametrize('quantity', [0, -1, 0.5, 1.9, 1.0, True, False, '2', None, MAX_ORDER_QUANTITY + 1])
def test_creation_rejects_invalid_quantity_in_both_dtos(quantity):
    with pytest.raises(ValidationError):
        CreateOrderProductItem(product_card_id=uuid4(), quantity=quantity)
    with pytest.raises(ValidationError):
        CreateOrderProductRequest(order_id=uuid4(), product_card_id=uuid4(), quantity=quantity)


@pytest.mark.parametrize('quantity', [1, MAX_ORDER_QUANTITY])
def test_creation_quantity_boundaries(quantity):
    assert CreateOrderProductItem(product_card_id=uuid4(), quantity=quantity).quantity == quantity
    assert CreateOrderProductRequest(order_id=uuid4(), product_card_id=uuid4(), quantity=quantity).quantity == quantity


@pytest.mark.parametrize('quantity', [0, -1, 0.5, 1.0, True, '2', None, MAX_ORDER_QUANTITY + 1])
def test_internal_capture_rejects_quantity_before_query(quantity):
    session = SimpleNamespace(execute=AsyncMock())
    with pytest.raises(HTTPException) as error:
        asyncio.run(capture_snapshot(session, uuid4(), uuid4(), quantity))
    assert error.value.status_code == 422
    session.execute.assert_not_awaited()
