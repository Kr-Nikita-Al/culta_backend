"""TLS-only SMTP delivery. No credentials, codes or server replies are logged."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from fastapi import HTTPException


def deliver_smtp(email, code, purpose='подтверждения email'):
    username = os.environ.get('SMTP_USERNAME', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    sender = os.environ.get('SMTP_FROM') or username
    host = os.environ.get('SMTP_HOST', 'smtp.mail.ru')
    security = os.environ.get('SMTP_SECURITY', 'ssl')
    try:
        port = int(os.environ.get('SMTP_PORT', '465'))
        if not username or not password or not sender or security not in ('ssl', 'starttls'):
            raise ValueError('Invalid SMTP configuration')
        message = EmailMessage()
        message['From'] = formataddr((os.environ.get('SMTP_FROM_NAME', 'Culta'), sender))
        message['To'] = email
        message['Subject'] = f'Culta — код {purpose}'
        message['Date'] = formatdate(localtime=False)
        message['Message-ID'] = make_msgid()
        message.set_content(f'Ваш код {purpose} Culta: {code}\n\n'
                            'Код действует 10 минут. Никому его не сообщайте.\n'
                            'Если вы не запрашивали код, проигнорируйте письмо.\n')
        context = ssl.create_default_context()
        client = (smtplib.SMTP_SSL(host, port, timeout=15, context=context) if security == 'ssl'
                  else smtplib.SMTP(host, port, timeout=15))
        with client as smtp:
            if security == 'starttls':
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(username, password)
            if smtp.send_message(message):
                raise smtplib.SMTPException('Recipient rejected')
    except (OSError, smtplib.SMTPException, ValueError):
        raise HTTPException(503, 'Email delivery temporarily unavailable') from None
