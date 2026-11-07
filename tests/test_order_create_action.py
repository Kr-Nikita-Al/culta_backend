"""One transaction must own the order, all positions and the total."""
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from db import STATUS_TYPE
from order.actions import create_order_action as action
from order.interface_request import CreateOrderRequest


def product_result(price, title='Coffee', cost_price='0.05'):
    return SimpleNamespace(one_or_none=lambda: SimpleNamespace(title=title, price=price, cost_price=cost_price))


@pytest.fixture
def context(monkeypatch):
    user_id, company_id = uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(order_id=uuid4(), company_id=company_id, user_id=user_id,
                          staff_id=user_id, creator_id=user_id, updater_id=user_id,
                          comment='', cocking_time=0, status=STATUS_TYPE.CREATED,
                          time_created=now, time_updated=now, price=0)
    transaction = AsyncMock()
    monkeypatch.setattr(action, 'assign_check', AsyncMock(return_value=uuid4()))
    session = SimpleNamespace(begin=lambda: transaction, execute=AsyncMock(), flush=AsyncMock())
    session.execute.side_effect = [product_result('0.10'), product_result('0.20')]
    order_dal = SimpleNamespace(create_order=AsyncMock(return_value=row))
    positions = SimpleNamespace(create_order_product=AsyncMock())
    monkeypatch.setattr(action, 'OrderDal', lambda db: order_dal if db is session else None)
    monkeypatch.setattr(action, 'OrderProductAssociationDal', lambda db: positions if db is session else None)
    body = CreateOrderRequest(company_id=company_id, user_id=user_id,
                              order_items=[{'product_card_id': uuid4(), 'quantity': 3},
                                           {'product_card_id': uuid4(), 'quantity': 2}])
    return SimpleNamespace(session=session, transaction=transaction, row=row,
                           positions=positions, body=body, user_id=user_id)


def create(ctx):
    return asyncio.run(action.__create_order(ctx.body, ctx.user_id, ctx.session))


def test_creation_commits_positions_and_total_together(context):
    result = create(context)
    assert result.price == context.row.price == Decimal('0.70')
    assert context.positions.create_order_product.await_count == 2
    for call in context.positions.create_order_product.await_args_list:
        assert call.args[0]['order_id'] == result.order_id
        assert call.args[0]['product_title'] == 'Coffee'
        assert call.args[0]['unit_cost_price'] == Decimal('0.05')
        assert call.args[0]['line_total'] == call.args[0]['unit_price'] * call.args[0]['quantity']
    context.session.flush.assert_awaited_once()
    context.transaction.__aenter__.assert_awaited_once()
    context.transaction.__aexit__.assert_awaited_once_with(None, None, None)


def test_failed_second_position_rolls_back_whole_transaction(context):
    context.positions.create_order_product.side_effect = [None, IntegrityError('', {}, Exception())]
    with pytest.raises(IntegrityError):
        create(context)
    assert context.positions.create_order_product.await_count == 2
    assert context.transaction.__aexit__.await_args.args[0] is IntegrityError


@pytest.mark.parametrize('price', [None, -1, float('nan'), float('inf')])
def test_invalid_second_product_rolls_back_first_position(context, price):
    context.session.execute.side_effect = [product_result(5), product_result(price)]
    with pytest.raises(HTTPException) as error:
        create(context)
    assert error.value.status_code == 422
    context.positions.create_order_product.assert_awaited_once()
    assert context.transaction.__aexit__.await_args.args[0] is HTTPException


def test_failed_total_flush_rolls_back_order_and_positions(context):
    context.session.flush.side_effect = IntegrityError('', {}, Exception())
    with pytest.raises(IntegrityError):
        create(context)
    assert context.transaction.__aexit__.await_args.args[0] is IntegrityError


def test_failed_commit_does_not_return_created_order(context):
    context.transaction.__aexit__.side_effect = IntegrityError('', {}, Exception())
    with pytest.raises(IntegrityError):
        create(context)


@pytest.mark.parametrize('items', [None, []])
def test_empty_order_has_zero_total(context, items):
    context.body.order_items = items
    assert create(context).price == 0
    context.positions.create_order_product.assert_not_awaited()
    context.session.execute.assert_not_awaited()
