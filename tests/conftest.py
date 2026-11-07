"""Isolated configuration: REST tests never connect to production services."""

import os
import pytest


def pytest_addoption(parser):
    parser.addoption('--integration', action='store_true', default=False,
                     help='Run integration tests on a dedicated local PostgreSQL database')


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--integration'):
        for item in items:
            if 'integration' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='Pass --integration to enable PostgreSQL tests'))


os.environ.update({
    'ENV': 'test',
    'REAL_DATABASE_URL': 'postgresql+asyncpg://test:test@127.0.0.1:9/culta_test',
    'APP_PORT': '8000',
    'ACCESS_SUPER_ADMINS': '',
    'SECRET_KEY': 'test-only-access-key',
    'ALGORITHM': 'HS256',
    'ACCESS_TOKEN_EXPIRE_MINUTES': '15',
    'QR_SECRET_KEY': 'test-only-qr-key',
    'QR_ALGORITHM': 'HS256',
    'AWS_BUCKET_NAME': 'test-only',
    'AWS_ACCESS_KEY_ID': 'test-only',
    'AWS_SECRET_ACCESS_KEY': 'test-only',
    'YANDEX_CLIENT_ID': 'test-only',
    'YANDEX_CLIENT_SECRET': 'test-only',
    'YANDEX_REDIRECT_URI': 'http://localhost/callback',
})
