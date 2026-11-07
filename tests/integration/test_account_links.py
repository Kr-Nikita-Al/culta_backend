import time
from urllib.parse import urlparse, parse_qs
import pytest
import rsa
import httpx
from jose import jwt, jwk
from sqlalchemy import select, update, func
from db import UserDB, AuthAccountDB, AuthProvider, UserRoleDB
from sqlalchemy.orm import Session
import settings

pytestmark=pytest.mark.integration


def start(pg,monkeypatch):
    monkeypatch.setattr(settings,'GOOGLE_CLIENT_ID','link-test-client')
    monkeypatch.setattr(settings,'GOOGLE_CLIENT_SECRET','link-test-secret')
    result=pg.client.post('/login/accounts/google/start',headers=pg.headers('client_a'))
    assert result.status_code==200,result.text
    return parse_qs(urlparse(result.json()['url']).query)


def provider(monkeypatch,params,subject='external-google'):
    public,private=rsa.newkeys(2048)
    token=jwt.encode({'iss':'https://accounts.google.com','aud':'link-test-client','exp':int(time.time())+600,
        'sub':subject,'email':'different-address@example.com','email_verified':True,'nonce':params['nonce'][0]},private.save_pkcs1().decode(),algorithm='RS256')
    class Provider:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):return httpx.Response(200,json={'id_token':token},request=httpx.Request('POST','https://oauth2.googleapis.com/token'))
        async def get(self,*args,**kwargs):return httpx.Response(200,json={'keys':[jwk.construct(public.save_pkcs1().decode(),'RS256').to_dict()]},request=httpx.Request('GET','https://www.googleapis.com/oauth2/v3/certs'))
    monkeypatch.setattr('auth.google_oauth.httpx.AsyncClient',Provider)


def callback(pg,params,role='client_a'):
    return pg.client.post('/login/auth/google/callback',headers=pg.headers(role) if role else {},
        json={'code':'provider-code','state':params['state'][0]})


def test_link_preserves_user_balance_roles_and_consumes_flow(pg,monkeypatch):
    with pg.engine.connect() as conn:
        users=conn.scalar(select(func.count()).select_from(UserDB))
        roles=conn.scalar(select(func.count()).select_from(UserRoleDB))
        wallet=conn.scalar(select(UserDB.bonus_balance).where(UserDB.user_id==pg.ids['client_a']))
    params=start(pg,monkeypatch)
    cookie=pg.client.cookies.get('culta_google_flow')
    provider(monkeypatch,params)
    assert callback(pg,params,role='client_b').status_code==400
    assert callback(pg,params,role=None).status_code==401
    response=callback(pg,params)
    assert response.status_code==200,response.text
    assert response.json()=={'linked':True,'provider':'google'}
    assert 'access_token' not in response.json()
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(UserDB))==users
        assert conn.scalar(select(func.count()).select_from(UserRoleDB))==roles
        assert conn.scalar(select(UserDB.bonus_balance).where(UserDB.user_id==pg.ids['client_a']))==wallet
        assert conn.scalar(select(AuthAccountDB.user_id).where(AuthAccountDB.provider_user_id=='external-google'))==pg.ids['client_a']
    pg.client.cookies.set('culta_google_flow',cookie,path='/login/auth/google')
    assert callback(pg,params).status_code==400
    methods=pg.client.get('/login/accounts',headers=pg.headers('client_a')).json()['providers']
    assert next(row for row in methods if row['provider']=='google')['linked'] is True


def test_existing_identity_is_not_transferred_or_logged_in(pg,monkeypatch):
    with Session(pg.engine) as db,db.begin():
        db.add(AuthAccountDB(provider=AuthProvider.GOOGLE,provider_user_id='other-google',user_id=pg.ids['client_b']))
    params=start(pg,monkeypatch);provider(monkeypatch,params,'other-google')
    result=callback(pg,params)
    assert result.status_code==200,result.text
    assert result.json()=={'linked':False,'separate_account':True}
    with pg.engine.connect() as conn:
        assert conn.scalar(select(AuthAccountDB.user_id).where(AuthAccountDB.provider_user_id=='other-google'))==pg.ids['client_b']
    candidates=pg.client.get('/login/account-suggestions',headers=pg.headers('client_a')).json()
    assert len(candidates)==1 and candidates[0]['status']=='verified'
    assert set(candidates[0])=={'id','status'}


def test_suggestions_are_private_and_dismissal_is_symmetric_and_durable(pg):
    # Placeholder phone values must never produce matches between every account.
    assert pg.client.get('/login/account-suggestions',headers=pg.headers('client_a')).json()==[]
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_b']).values(surname='client_a'))
    result=pg.client.get('/login/account-suggestions',headers=pg.headers('client_a')).json()
    assert len(result)==1
    sid=result[0]['id']
    assert pg.client.post('/login/account-suggestions/'+sid+'/dismiss',headers=pg.headers('admin_a')).status_code==404
    assert pg.client.post('/login/account-suggestions/'+sid+'/dismiss',headers=pg.headers('client_a')).status_code==200
    for role in ('client_a','client_b'):
        assert pg.client.get('/login/account-suggestions',headers=pg.headers(role)).json()==[]


def test_yandex_email_match_never_links_implicitly(pg):
    import asyncio
    from fastapi import HTTPException
    from auth.actions_by_yandex.get_or_create_auth_user_action import __get_or_create_auth_user
    async def run():
        async with pg.sessions() as db:
            await __get_or_create_auth_user(db,AuthProvider.YANDEX,'new-yandex',email='client_a@example.test')
    with pytest.raises(HTTPException) as error:
        asyncio.run(run())
    assert error.value.status_code==409
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(AuthAccountDB))==0


def matched_pair(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_b']).values(surname='client_a'))
    return pg.client.get('/login/account-suggestions',headers=pg.headers('client_a')).json()[0]['id']


def test_verification_wrong_provider_identity_does_not_connect_it(pg,monkeypatch):
    sid=matched_pair(pg)
    monkeypatch.setattr(settings,'GOOGLE_CLIENT_ID','link-test-client')
    monkeypatch.setattr(settings,'GOOGLE_CLIENT_SECRET','link-test-secret')
    result=pg.client.post('/login/accounts/google/start',json={'suggestion_id':sid},headers=pg.headers('client_a'))
    params=parse_qs(urlparse(result.json()['url']).query)
    provider(monkeypatch,params,'unrelated-identity')
    response=callback(pg,params)
    assert response.status_code==200,response.text
    assert response.json()['verification_failed'] is True
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(AuthAccountDB))==0


def test_verify_password_never_switches_session_and_is_rate_limited(pg):
    from tests.integration.conftest import PASSWORD
    sid=matched_pair(pg)
    url='/login/account-suggestions/'+sid+'/verify-password'
    response=pg.client.post(url,json={'email':'client_b@example.test','password':PASSWORD},headers=pg.headers('client_a'))
    assert response.status_code==200,response.text
    assert response.json()=={'verified':True,'merged':False}
    for _ in range(4):
        assert pg.client.post(url,json={'email':'client_b@example.test','password':'bad'},headers=pg.headers('client_a')).status_code==400
    assert pg.client.post(url,json={'email':'client_b@example.test','password':PASSWORD},headers=pg.headers('client_a')).status_code==429
    assert pg.client.post(url,json={'email':'client_b@example.test','password':PASSWORD},headers=pg.headers('admin_a')).status_code==404


def test_phone_normalization_and_stale_matches(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_a']).values(phone='+79991234567'))
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_b']).values(phone='89991234567'))
    result=pg.client.get('/login/account-suggestions',headers=pg.headers('client_a'))
    assert result.status_code==200,result.text
    assert len(result.json())==1
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_b']).values(phone='89997654321'))
    assert pg.client.get('/login/account-suggestions',headers=pg.headers('client_a')).json()==[]
