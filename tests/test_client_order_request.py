from uuid import uuid4
import pytest
from pydantic import ValidationError
from order.client_schemas import ClientOrderRequest


def request(**changes):
    return {'company_id': uuid4(), 'request_id': uuid4(), 'context': 'outside',
            'order_items': [{'product_card_id': uuid4(), 'quantity': 1}], **changes}


@pytest.mark.parametrize('quantity', [0, -1, 1.5, True, '1'])
def test_strict_positive_client_quantity(quantity):
    with pytest.raises(ValidationError):
        ClientOrderRequest(**request(order_items=[{'product_card_id': uuid4(), 'quantity': quantity}]))


def test_client_items_reject_price_and_duplicates():
    item = {'product_card_id': uuid4(), 'quantity': 1}
    for items in ([{**item, 'price': '0'}], [item, item], []):
        with pytest.raises(ValidationError):
            ClientOrderRequest(**request(order_items=items))


def test_outside_cannot_supply_table_token():
    with pytest.raises(ValidationError):
        ClientOrderRequest(**request(table_token='x' * 80))
