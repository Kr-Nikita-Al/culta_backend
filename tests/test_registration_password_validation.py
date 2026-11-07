import pytest
from pydantic import ValidationError
from user.interface_request.create_user_request import CreateUserRequest

@pytest.mark.parametrize('password', ['a'*72, 'я'*36, '😀'*18])
def test_accepts_passwords_at_byte_limit(password):
    body = CreateUserRequest(name='Тест', surname='Тест', phone='+79990000000',
                             email='test@example.com', password=password)
    assert body.password == password

@pytest.mark.parametrize('password', ['a'*73, 'я'*37, '😀'*19, 'short', ''])
def test_rejects_invalid_passwords(password):
    with pytest.raises(ValidationError):
        CreateUserRequest(name='Тест', surname='Тест', phone='+79990000000',
                          email='test@example.com', password=password)
