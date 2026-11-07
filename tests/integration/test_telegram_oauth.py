import pytest
import time
import hashlib
import base64
from urllib.parse import urlparse,parse_qs
from jose import jwt,jwk
import rsa
import settings
pytestmark=pytest.mark.integration


def test_telegram_flow(pg,monkeypatch):
    monkeypatch.setattr(settings,'ACCESS_SUPER_ADMINS',[' TELEGRAM-USER@EXAMPLE.COM '])
    monkeypatch.setattr(settings,'TELEGRAM_CLIENT_ID','test-client')
    monkeypatch.setattr(settings,'TELEGRAM_CLIENT_SECRET','test-secret')
    start=pg.client.post('/login/auth/telegram/start')
    assert start.status_code==200
    assert 'HttpOnly' in start.headers['set-cookie']
    params=parse_qs(urlparse(start.json()['url']).query)
    assert params['code_challenge_method']==['S256']
    assert pg.client.post('/login/auth/telegram/callback',json={'code':'x','state':'wrong'}).status_code==400
    public_key,private_key=rsa.newkeys(2048)
    private=private_key.save_pkcs1().decode()
    public=public_key.save_pkcs1().decode()
    identity=jwt.encode({'iss':'https://oauth.telegram.org','aud':'test-client','exp':int(time.time())+600,'sub':'telegram-user','email':'telegram-user@example.com','email_verified':True,'nonce':params['nonce'][0],'given_name':'Test','family_name':'Telegram'},private,algorithm='RS256')
    import auth.telegram_oauth as telegram
    import httpx
    class Provider:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):
            assert kwargs['data']['code_verifier']
            return httpx.Response(200,json={'id_token':identity,'access_token':'telegram-access-token'},request=httpx.Request('POST','https://oauth.telegram.org/token'))
        async def get(self,*args,**kwargs):
            return httpx.Response(200,json={'keys':[jwk.construct(public,'RS256').to_dict()]},request=httpx.Request('GET','https://oauth.telegram.org/.well-known/jwks.json'))
    monkeypatch.setattr(telegram.httpx,'AsyncClient',Provider)
    claims_with_hash=jwt.get_unverified_claims(identity)
    claims_with_hash['at_hash']=base64.urlsafe_b64encode(hashlib.sha256(b'telegram-access-token').digest()[:16]).rstrip(b'=').decode()
    identity=jwt.encode(claims_with_hash,private,algorithm='RS256')
    valid_identity=identity
    claims=jwt.get_unverified_claims(identity)
    for invalid in ({'nonce':'wrong'}, {'aud':'other-client'}, {'iss':'https://other.example'}):
        identity=jwt.encode({**claims,**invalid},private,algorithm='RS256')
        rejected=pg.client.post('/login/auth/telegram/callback',json={'code':'test-code','state':params['state'][0]})
        assert rejected.status_code==400,rejected.text
    identity=valid_identity
    response=pg.client.post('/login/auth/telegram/callback',json={'code':'test-code','state':params['state'][0]})
    assert response.status_code==200,response.text
    assert response.json()['refresh_token']
    headers={'Authorization':'Bearer '+response.json()['access_token']}
    assert pg.client.get('/login/token/status',headers=headers).status_code==200
    refreshed=pg.client.post('/login/refresh',json={'refresh_token':response.json()['refresh_token']})
    assert refreshed.status_code==200,refreshed.text
    from sqlalchemy import select,func
    from db import UserRoleDB
    from uuid import UUID
    with pg.engine.connect() as connection:
        count=connection.scalar(select(func.count()).select_from(UserRoleDB).where(
            UserRoleDB.user_id==UUID(response.json()['user_id']),
            UserRoleDB.role=='PORTAL_ROLE_SUPER_ADMIN',UserRoleDB.is_active.is_(True)))
        assert count==0
    assert pg.client.post('/login/auth/telegram/callback',json={'code':'test-code','state':params['state'][0]}).status_code==400
    from db import UserDB
    with pg.engine.connect() as connection:
        assert connection.scalar(select(UserDB.email).where(UserDB.user_id==UUID(response.json()['user_id']))) is None
    # A second login reuses the same account, rather than issuing another welcome balance.
    start=pg.client.post('/login/auth/telegram/start')
    params=parse_qs(urlparse(start.json()['url']).query)
    identity=jwt.encode({**claims,'nonce':params['nonce'][0]},private,algorithm='RS256')
    again=pg.client.post('/login/auth/telegram/callback',json={'code':'second-code','state':params['state'][0]})
    assert again.status_code==200,again.text
    assert again.json()['user_id']==response.json()['user_id']
