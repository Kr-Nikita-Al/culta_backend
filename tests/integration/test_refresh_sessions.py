import pytest
from sqlalchemy import text
pytestmark = pytest.mark.integration


def start(pg):
    response=pg.client.post('/login/session',json={'email':'admin_a@example.test','password':'integration-only-password'})
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    return response.json()['refresh_token']


def refresh(pg, token):
    return pg.client.post('/login/refresh',json={'refresh_token':token})


def test_rotation_replay_and_logout(pg):
    first=start(pg)
    second=refresh(pg,first)
    assert second.status_code==200,second.text
    second=second.json()['refresh_token']
    assert first != second
    assert refresh(pg,first).status_code==401
    assert refresh(pg,second).status_code==401
    third=start(pg)
    assert refresh(pg,third.split('.')[0]+'.fake').status_code==401
    fourth=refresh(pg,third).json()['refresh_token']
    assert pg.client.post('/login/logout',json={'refresh_token':fourth}).status_code==200
    assert refresh(pg,fourth).status_code==401
    with pg.engine.connect() as conn:
        hashes=conn.execute(text('SELECT token_hash FROM refresh_session')).scalars().all()
        assert all(len(value)==64 and value not in (first,second,third,fourth) for value in hashes)


def test_logout_immediately_invalidates_session_access_token(pg):
    response=pg.client.post('/login/session',json={'email':'admin_a@example.test','password':'integration-only-password'})
    data=response.json()
    headers={'Authorization':'Bearer '+data['access_token']}
    status=pg.client.get('/login/token/status',headers=headers)
    assert status.status_code==200,status.text
    assert 0 < status.json()['expires_in'] <= 900
    assert pg.client.post('/login/logout',json={'refresh_token':data['refresh_token']}).status_code==200
    assert pg.client.get('/login/token/status',headers=headers).status_code==401
    assert pg.client.get('/user_role/get_user_roles',headers=headers).status_code==401


def test_only_owner_can_list_and_revoke_sessions(pg):
    token=start(pg)
    sid=token.split('.')[0]
    own=pg.client.get('/login/sessions',headers=pg.headers()).json()
    assert any(row['session_id']==sid for row in own)
    assert all(set(row)=={'session_id','expires_at'} for row in own)
    assert pg.client.get('/login/sessions',headers=pg.headers('admin_b')).json()==[]
    assert pg.client.delete('/login/sessions/'+sid,headers=pg.headers('admin_b')).status_code==404
    assert pg.client.delete('/login/sessions/'+sid,headers=pg.headers()).status_code==200
    assert refresh(pg,token).status_code==401


def test_expiry_and_account_state(pg):
    token=start(pg)
    with pg.engine.begin() as conn:
        conn.execute(text("UPDATE refresh_session SET expires_at=now()-interval '1 second'"))
    assert refresh(pg,token).status_code==401
    token=start(pg)
    with pg.engine.begin() as conn:
        conn.execute(text('UPDATE "user" SET account_status=:state WHERE user_id=:id'),{'state':'blocked','id':pg.ids['admin_a']})
    assert refresh(pg,token).status_code==401
    assert pg.client.post('/login/session',json={'email':'admin_a@example.test','password':'integration-only-password'}).status_code==403


def test_password_change_invalidates_refresh(pg):
    token=start(pg)
    with pg.engine.begin() as conn:
        conn.execute(text('UPDATE "user" SET hashed_password=:value WHERE user_id=:id'),{'value':'changed-password-hash','id':pg.ids['admin_a']})
    assert refresh(pg,token).status_code==401


def test_yandex_callback_issues_refresh_session(pg, monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import urlparse, parse_qs
    import auth.api_handlers as handlers
    class Provider:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs):
            return SimpleNamespace(status_code=200,json=lambda:{'access_token':'provider-token'})
        async def get(self,*args,**kwargs):
            return SimpleNamespace(status_code=200,json=lambda:{'id':'provider-id','default_email':'admin_a@example.test','default_phone':{'number':'00000000000'}})
    async def existing(db,**kwargs):
        from user.actions.get_current_user_from_token_action import __get_user_by_email_for_auth
        return await __get_user_by_email_for_auth('admin_a@example.test',db)
    monkeypatch.setattr(handlers.httpx,'AsyncClient',Provider)
    monkeypatch.setattr(handlers,'__get_or_create_auth_user',existing)
    start_response=pg.client.get('/login/auth/yandex',follow_redirects=False)
    state=parse_qs(urlparse(start_response.headers['location']).query)['state'][0]
    response=pg.client.get('/login/auth/yandex/callback',params={'code':'test-code','state':state})
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    assert refresh(pg,response.json()['refresh_token']).status_code==200
