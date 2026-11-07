"""Company-level client ordering configuration and legacy compatibility."""
import pytest
from sqlalchemy import update
from db import CompanyDB

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def valid_company_email(pg):
    # Public company DTO validates EmailStr; .test fixture domains are rejected.
    with pg.engine.begin() as connection:
        connection.execute(update(CompanyDB).values(email='company@example.com'))


def patch(pg, data, role='admin_a'):
    return pg.client.patch('/company/update_by_id',
        params={'company_id': str(pg.ids['company_a'])}, headers=pg.headers(role), json=data)


def settings(pg):
    response = pg.client.get('/company/get_by_id', params={'company_id': str(pg.ids['company_a'])})
    assert response.status_code == 200, response.text
    data = response.json()
    return tuple(data[key] for key in (
        'allow_client_orders_inside', 'allow_client_orders_outside', 'is_can_client_create_order'))


def test_independent_settings_and_legacy_updates(pg):
    assert settings(pg) == (False, False, False)
    assert patch(pg, {'allow_client_orders_inside': True}).status_code == 200
    assert settings(pg) == (True, False, True)
    assert patch(pg, {'allow_client_orders_outside': True}).status_code == 200
    assert settings(pg) == (True, True, True)
    assert patch(pg, {'allow_client_orders_inside': False}).status_code == 200
    assert settings(pg) == (False, True, True)
    assert patch(pg, {'is_can_client_create_order': False}).status_code == 200
    assert settings(pg) == (False, False, False)
    assert patch(pg, {'is_can_client_create_order': True, 'allow_client_orders_outside': False}).status_code == 200
    assert settings(pg) == (True, False, True)


@pytest.mark.parametrize('role', ['client_a', 'waiter_a', 'cook_a', 'admin_b'])
def test_settings_require_management_in_same_company(pg, role):
    assert patch(pg, {'allow_client_orders_inside': True}, role).status_code == 403
    assert settings(pg) == (False, False, False)


@pytest.mark.parametrize('value', ['true', 1, [], {}])
def test_settings_reject_non_boolean_values(pg, value):
    assert patch(pg, {'allow_client_orders_inside': value}).status_code == 422
    assert settings(pg) == (False, False, False)
