"""Capture catalog values once, inside the order's transaction."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select

from db import ProductCardDB
from utils.money import CENT, MAX_MONEY
from utils.order_quantity import MAX_ORDER_QUANTITY


def line_total(unit_price: Decimal, quantity: int) -> Decimal:
    if quantity < 0:
        raise HTTPException(422, 'Invalid quantity')
    total = unit_price * quantity
    if not total.is_finite() or total < 0 or total > MAX_MONEY:
        raise HTTPException(422, 'Order position total exceeds the supported amount')
    return total.quantize(CENT)


async def capture_snapshot(session, company_id, product_card_id, quantity):
    # Also protect internal callers that do not pass through a request DTO.
    if type(quantity) is not int or not 1 <= quantity <= MAX_ORDER_QUANTITY:
        raise HTTPException(422, 'Quantity must be a positive integer within the supported range')
    result = await session.execute(
        select(ProductCardDB.title, ProductCardDB.price, ProductCardDB.cost_price).where(
            ProductCardDB.product_card_id == product_card_id,
            ProductCardDB.company_id == company_id,
            ProductCardDB.is_active.is_(True),
        ).with_for_update(read=True)
    )
    product = result.one_or_none()
    if product is None:
        raise HTTPException(422, 'Product is unavailable in this company')
    if product.title is None:
        raise HTTPException(422, 'Invalid product title')
    amounts = {}
    for field, value in [('unit_price', product.price), ('unit_cost_price', product.cost_price)]:
        if value is None:
            raise HTTPException(422, 'Invalid product amount')
        amount = Decimal(str(value))
        if not amount.is_finite() or not 0 <= amount <= MAX_MONEY or amount != amount.quantize(CENT):
            raise HTTPException(422, 'Invalid product amount')
        amounts[field] = amount
    return {'product_title': product.title, **amounts,
            'line_total': line_total(amounts['unit_price'], quantity)}
