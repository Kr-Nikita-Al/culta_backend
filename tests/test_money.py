from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from product_card.interface_request.create_product_card_request import CreateProductCardRequest
from product_card.interface_request.update_product_card_request import UpdateProductCardRequest
from company.interface_request.update_company_request import UpdateCompanyRequest
from user.interface_request.update_bonus_balance_request import UpdateBonusBalanceRequest
from utils.base_model_response import BaseModelResponse
from utils.money import MoneyResponse, PercentageResponse


@pytest.mark.parametrize('value', ['0.10', 0.1, '9999999999999999.99', '0', None])
def test_money_inputs(value):
    result = CreateProductCardRequest(company_id=uuid4(), price=value)
    assert result.price == (None if value is None else Decimal(str(value)))


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity', -1, '0.001', '10000000000000000', True])
def test_reject_invalid_money(value):
    with pytest.raises(ValidationError):
        UpdateProductCardRequest(price=value)


@pytest.mark.parametrize('value', [-1, 101, '0.001', 'NaN'])
def test_reject_invalid_percent(value):
    with pytest.raises(ValidationError):
        UpdateCompanyRequest(bonus_payment_perc=value)
    with pytest.raises(ValidationError):
        UpdateProductCardRequest(cashback_perc=value)


def test_bonus_uses_decimal():
    request = UpdateBonusBalanceRequest(company_id=uuid4(), amount=0.1, is_write_off=False,
                                       request_id=uuid4(), reason='Correction')
    assert isinstance(request.amount, Decimal)
    assert Decimal('500.00') + request.amount * 3 == Decimal('500.30')
    with pytest.raises(ValidationError):
        UpdateBonusBalanceRequest(company_id=uuid4(), amount=-1, is_write_off=False)


def test_response_encoding_and_schema():
    class Response(BaseModelResponse):
        price: MoneyResponse
        percentage: PercentageResponse

    response = Response(price='9999999999999999.99', percentage=5)
    assert jsonable_encoder(response) == {'price': '9999999999999999.99', 'percentage': '5.00'}
    assert Response.schema()['properties']['price']['type'] == 'string'
