from uuid import uuid4
import pytest
from pydantic import ValidationError
from user.interface_request import UpdateBonusBalanceRequest


@pytest.mark.parametrize('changes', [
    {'amount': 0}, {'amount': -1}, {'amount': '0.001'}, {'amount': 'NaN'},
    {'reason': '  '}, {'reason': 'x' * 501}, {'request_id': None},
    {'is_write_off': 'false'}, {'balance_after': 100}, {'amount': True},
])
def test_invalid_bonus_correction(changes):
    body = dict(company_id=uuid4(), request_id=uuid4(), reason='Correction', amount='1.00', is_write_off=False)
    with pytest.raises(ValidationError):
        UpdateBonusBalanceRequest(**{**body, **changes})
