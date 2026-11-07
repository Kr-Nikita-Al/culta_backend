"""Unit tests for PATCH transaction boundaries and status revalidation."""

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from db import STATUS_TYPE
from order.actions import update_order_action as action
from order.interface_request.create_order_request import OrderProductItem


@pytest.fixture
def context(monkeypatch):
    transaction = AsyncMock()
    session = SimpleNamespace(begin=lambda: transaction)
    order_id = uuid4()
    dal = SimpleNamespace(get_order_status_for_update=AsyncMock(return_value=STATUS_TYPE.CREATED),
                          update_order=AsyncMock(return_value=order_id))
    positions = SimpleNamespace(update_order_product=AsyncMock(return_value=uuid4()),
                                calculate_order_total=AsyncMock(return_value=Decimal('12.50')))
    monkeypatch.setattr(action, 'OrderDal', lambda _: dal)
    monkeypatch.setattr(action, 'OrderProductAssociationDal', lambda _: positions)
    return SimpleNamespace(transaction=transaction, session=session, order_id=order_id,
                           dal=dal, positions=positions)


def update(ctx, items=None):
    return asyncio.run(action.__update_order_by_id(
        {'comment': 'changed'}, ctx.order_id, ctx.session,
        order_items=items, expected_status=STATUS_TYPE.CREATED,
    ))


@pytest.mark.parametrize('status, expected', [
    (None, 404), (STATUS_TYPE.CLOSED, 409), (STATUS_TYPE.CANCELED, 409),
    (STATUS_TYPE.PROCESSING, 409),
])
def test_changed_status_is_rejected_after_lock_before_writes(context, status, expected):
    context.dal.get_order_status_for_update.return_value = status
    with pytest.raises(HTTPException) as exc:
        update(context, [OrderProductItem(product_card_id=uuid4(), quantity=2)])
    assert exc.value.status_code == expected
    context.positions.update_order_product.assert_not_awaited()
    context.dal.update_order.assert_not_awaited()
    assert context.transaction.__aexit__.await_args.args[0] is HTTPException


def test_missing_second_position_exits_transaction_with_error(context):
    context.positions.update_order_product.side_effect = [uuid4(), None]
    with pytest.raises(HTTPException) as exc:
        update(context, [OrderProductItem(product_card_id=uuid4(), quantity=2),
                         OrderProductItem(product_card_id=uuid4(), quantity=3)])
    assert exc.value.status_code == 404
    context.dal.update_order.assert_not_awaited()
    # The exception reaches session.begin(), so SQLAlchemy rolls back all writes.
    assert context.transaction.__aexit__.await_args.args[0] is HTTPException


def test_failed_order_update_rolls_back_position_changes(context):
    context.dal.update_order.return_value = None
    with pytest.raises(HTTPException) as exc:
        update(context, [OrderProductItem(product_card_id=uuid4(), quantity=2)])
    assert exc.value.status_code == 409
    assert context.transaction.__aexit__.await_args.args[0] is HTTPException


def test_successful_update_commits_positions_and_order_together(context):
    assert update(context, [OrderProductItem(product_card_id=uuid4(), quantity=2)]) == context.order_id
    context.transaction.__aenter__.assert_awaited_once()
    context.transaction.__aexit__.assert_awaited_once_with(None, None, None)
    context.positions.update_order_product.assert_awaited_once()
    context.dal.update_order.assert_awaited_once()
    assert context.dal.update_order.await_args.kwargs['price'] == Decimal('12.50')


def test_metadata_edit_does_not_recalculate_legacy_total(context):
    update(context)
    context.positions.calculate_order_total.assert_not_awaited()
    assert 'price' not in context.dal.update_order.await_args.kwargs


def test_total_failure_rolls_back_all_edits(context):
    context.positions.calculate_order_total.side_effect = HTTPException(422, 'Overflow')
    with pytest.raises(HTTPException):
        update(context, [OrderProductItem(product_card_id=uuid4(), quantity=2)])
    context.dal.update_order.assert_not_awaited()
    assert context.transaction.__aexit__.await_args.args[0] is HTTPException
