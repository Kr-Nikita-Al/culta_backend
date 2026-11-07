from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlparse, parse_qs
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
import settings
from auth import api_handlers as api
from utils.constants import EMPTY_PHONE


@pytest.fixture
def flow(monkeypatch):
    app=FastAPI()
    app.include_router(api.login_router,prefix='/login')
    app.dependency_overrides[api.get_db]=lambda: object()
    user=SimpleNamespace(user_id='test-user')
    create=AsyncMock(return_value=user)
    monkeypatch.setattr(api,'__get_or_create_auth_user',create)
    monkeypatch.setattr('auth.email_confirmation.confirm_yandex_user',AsyncMock(return_value=user))
    monkeypatch.setattr('auth.refresh_sessions.issue_session',AsyncMock(return_value={'access_token':'test-token'}))
    return TestClient(app),create


@pytest.mark.parametrize('kind',['missing','wrong','expired','tampered'])
def test_invalid_state_never_exchanges_code(flow,monkeypatch,kind):
    client,create=flow
    outbound=AsyncMock()
    monkeypatch.setattr(api.httpx.AsyncClient,'post',outbound)
    start=client.get('/login/auth/yandex',allow_redirects=False)
    state=parse_qs(urlparse(start.headers['location']).query)['state'][0]
    if kind=='missing': client.cookies.clear()
    if kind=='wrong': state='wrong'
    if kind in ('expired','tampered'):
        client.cookies.clear()
        token=jwt.encode({'state':state,'purpose':'yandex-login','exp':int(time.time())-1},settings.SECRET_KEY,algorithm='HS256')
        client.cookies.set('culta_yandex_flow',token if kind=='expired' else 'invalid')
    response=client.get('/login/auth/yandex/callback',params={'code':'test-code','state':state})
    assert response.status_code==400
    outbound.assert_not_called()
    create.assert_not_called()


@pytest.mark.parametrize('phone',[None,{},'invalid',{'number':None},{'number':'89999999999'}])
def test_phone_optional_and_success_consumes_browser_cookie(flow,monkeypatch,phone):
    client,create=flow
    start=client.get('/login/auth/yandex',allow_redirects=False)
    assert 'HttpOnly' in start.headers['set-cookie']
    assert start.headers['cache-control']=='no-store'
    state=parse_qs(urlparse(start.headers['location']).query)['state'][0]
    monkeypatch.setattr(api.httpx.AsyncClient,'post',AsyncMock(return_value=SimpleNamespace(status_code=200,json=lambda:{'access_token':'provider-token'})))
    monkeypatch.setattr(api.httpx.AsyncClient,'get',AsyncMock(return_value=SimpleNamespace(status_code=200,json=lambda:{'id':'provider-id','default_email':'user@example.com','first_name':'Test','last_name':'User','default_phone':phone})))
    response=client.get('/login/auth/yandex/callback',params={'code':'test-code','state':state})
    assert response.status_code==200
    assert create.call_args.kwargs['phone']==EMPTY_PHONE
    assert 'culta_yandex_flow' not in client.cookies
    assert client.get('/login/auth/yandex/callback',params={'code':'test-code','state':state}).status_code==400
