from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from auth.smtp_delivery import deliver_smtp


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setenv('SMTP_USERNAME','test@example.com')
    monkeypatch.setenv('SMTP_PASSWORD','test-only')
    monkeypatch.setenv('SMTP_FROM','test@example.com')
    monkeypatch.setenv('SMTP_SECURITY','ssl')
    client=MagicMock()
    client.return_value.__enter__.return_value.send_message.return_value={}
    monkeypatch.setattr('auth.smtp_delivery.smtplib.SMTP_SSL',client)
    return client


def test_tls_message(smtp):
    deliver_smtp('recipient@example.com','123456')
    server=smtp.return_value.__enter__.return_value
    server.login.assert_called_once_with('test@example.com','test-only')
    message=server.send_message.call_args.args[0]
    assert message['To']=='recipient@example.com'
    assert '123456' in message.get_content()
    assert smtp.call_args.kwargs['context'].check_hostname


def test_smtp_failure_is_sanitized(smtp):
    import smtplib
    smtp.return_value.__enter__.return_value.login.side_effect=smtplib.SMTPAuthenticationError(535,b'secret reply')
    with pytest.raises(HTTPException) as error:deliver_smtp('a@example.com','123456')
    assert error.value.status_code==503
    assert 'secret' not in error.value.detail


def test_plaintext_rejected(smtp,monkeypatch):
    monkeypatch.setenv('SMTP_SECURITY','none')
    with pytest.raises(HTTPException):deliver_smtp('a@example.com','123456')
    smtp.assert_not_called()
