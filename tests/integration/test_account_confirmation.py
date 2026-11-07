import json
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select, update
from db import UserDB, UserRoleDB
from tests.integration.conftest import PASSWORD
from utils.constants import EMPTY_UUID, PortalRole

pytestmark = pytest.mark.integration


def pending(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id == pg.ids['client_a']).values(account_status='pending'))


def credentials():
    return {'email':'client_a@example.test', 'password':PASSWORD}


def test_configured_superadmin_requires_email_proof(pg,monkeypatch,tmp_path):
    import settings
    monkeypatch.setattr(settings,'ACCESS_SUPER_ADMINS',['client_a@example.test'])
    monkeypatch.setattr('user_role.api_handlers.ACCESS_SUPER_ADMINS',['client_a@example.test'])
    token = pg.token('client_a')
    pending(pg)
    login={'username':credentials()['email'],'password':'wrong'}
    assert pg.client.post('/login/token',data=login).status_code==401
    with pg.engine.connect() as conn:
        assert conn.scalar(select(UserDB.account_status).where(UserDB.user_id==pg.ids['client_a']))=='pending'
    login['password']=PASSWORD
    assert pg.client.post('/login/token',data=login).status_code==403
    headers={'Authorization':'Bearer '+token}
    assert pg.client.post('/user_role/grant_super_admin_privilege',headers=headers).status_code==403
    with pg.engine.connect() as conn:
        assert conn.scalar(select(UserDB.account_status).where(UserDB.user_id==pg.ids['client_a']))=='pending'
        assert conn.scalar(select(UserRoleDB.relation_id).where(UserRoleDB.user_id==pg.ids['client_a'],UserRoleDB.role==PortalRole.PORTAL_ROLE_SUPER_ADMIN)) is None
    local_delivery(monkeypatch,tmp_path)
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==200
    code=json.loads(next(tmp_path.glob('*.json')).read_text())['code']
    assert pg.client.post('/login/email/confirm',json={**credentials(),'code':code}).status_code==200
    assert pg.client.post('/login/token',data=login).status_code==200
    assert pg.client.post('/user_role/grant_super_admin_privilege',headers=headers).status_code==200
    with pg.engine.begin() as conn:
        assert conn.scalar(select(UserDB.account_status).where(UserDB.user_id==pg.ids['client_a']))=='confirmed'
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_a']).values(account_status='blocked'))
    assert pg.client.post('/login/token',data=login).status_code==403


def test_smtp_confirmation_and_delivery_failure_rollback(pg,monkeypatch):
    from fastapi import HTTPException
    pending(pg)
    monkeypatch.setenv('EMAIL_DELIVERY_MODE','smtp')
    def fail(email,code):raise HTTPException(503,'Email delivery temporarily unavailable')
    monkeypatch.setattr('auth.smtp_delivery.deliver_smtp',fail)
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==503
    with pg.engine.connect() as conn:
        assert conn.scalar(select(UserDB.email_code_hash).where(UserDB.user_id==pg.ids['client_a'])) is None
    delivered=[]
    monkeypatch.setattr('auth.smtp_delivery.deliver_smtp',lambda email,code:delivered.append((email,code)))
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==200
    assert len(delivered)==1 and delivered[0][0]==credentials()['email']
    assert pg.client.post('/login/email/confirm',json={**credentials(),'code':delivered[0][1]}).status_code==200


def local_delivery(monkeypatch, tmp_path):
    import settings
    monkeypatch.setattr(settings, 'ENV', 'local')
    monkeypatch.setenv('EMAIL_DELIVERY_MODE', 'local')
    monkeypatch.setenv('EMAIL_LOCAL_OUTBOX', str(tmp_path))


def test_pending_code_single_use_and_access(pg, monkeypatch, tmp_path):
    token = pg.token('client_a')
    pending(pg); local_delivery(monkeypatch,tmp_path)
    assert pg.client.get('/user/get_by_id', params={'user_id':str(pg.ids['client_a'])}, headers={'Authorization':'Bearer '+token}).status_code==403
    assert pg.client.post('/login/token',data={'username':credentials()['email'],'password':PASSWORD}).status_code==403
    response=pg.client.post('/login/email/request-code',json=credentials())
    assert response.status_code==200, response.text
    assert 'code' not in response.json()
    path=next(tmp_path.glob('*.json')); code=json.loads(path.read_text())['code']
    assert path.stat().st_mode & 0o777 == 0o600
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==429
    result=pg.client.post('/login/email/confirm',json={**credentials(),'code':code})
    assert result.status_code==200, result.text
    assert pg.client.post('/login/email/confirm',json={**credentials(),'code':code}).status_code==400
    assert pg.client.post('/login/token',data={'username':credentials()['email'],'password':PASSWORD}).status_code==200


def test_five_wrong_attempts_are_committed(pg, monkeypatch,tmp_path):
    pending(pg);local_delivery(monkeypatch,tmp_path)
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==200
    code=json.loads(next(tmp_path.glob('*.json')).read_text())['code']
    wrong='000000' if code!='000000' else '111111'
    for _ in range(5):
        assert pg.client.post('/login/email/confirm',json={**credentials(),'code':wrong}).status_code==400
    assert pg.client.post('/login/email/confirm',json={**credentials(),'code':code}).status_code==400
    with pg.engine.connect() as conn:
        assert conn.scalar(select(UserDB.email_code_attempts).where(UserDB.user_id==pg.ids['client_a']))==5


def test_expiry_resend_and_disabled_delivery(pg,monkeypatch,tmp_path):
    pending(pg);local_delivery(monkeypatch,tmp_path)
    pg.client.post('/login/email/request-code',json=credentials())
    code=json.loads(next(tmp_path.glob('*.json')).read_text())['code']
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_a']).values(
            email_code_expires=datetime.now(timezone.utc)-timedelta(seconds=1),
            email_code_sent_at=datetime.now(timezone.utc)-timedelta(seconds=61)))
    assert pg.client.post('/login/email/confirm',json={**credentials(),'code':code}).status_code==400
    import settings
    monkeypatch.setattr(settings,'ENV','production')
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==503
    assert len(list(tmp_path.glob('*.json')))==1


def test_global_status_permissions_and_existing_token(pg):
    token=pg.token('client_a')
    body={'status':'blocked','expected_status':'confirmed'}
    params={'user_id':str(pg.ids['client_a'])}
    assert pg.client.patch('/user/account_status',params=params,headers=pg.headers(),json=body).status_code==403
    with pg.engine.begin() as conn:
        conn.execute(UserRoleDB.__table__.insert().values(user_id=pg.ids['admin_a'],company_id=EMPTY_UUID,role=PortalRole.PORTAL_ROLE_SUPER_ADMIN))
    result=pg.client.patch('/user/account_status',params=params,headers=pg.headers(),json=body)
    assert result.status_code==200,result.text
    assert pg.client.get('/user/get_by_id',params=params,headers={'Authorization':'Bearer '+token}).status_code==403
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==403
    assert pg.client.patch('/user/account_status',params=params,headers=pg.headers(),json=body).status_code==409
    assert pg.client.patch('/user/account_status',params={'user_id':str(pg.ids['admin_a'])},headers=pg.headers(),json=body).status_code==403


def test_yandex_cannot_revive_blocked_account(pg):
    from auth.email_confirmation import confirm_yandex_user
    from fastapi import HTTPException
    async def confirm():
        async with pg.sessions() as session:
            return await confirm_yandex_user(session,pg.ids['client_a'])
    pending(pg)
    assert asyncio.run(confirm()).account_status=='confirmed'
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_a']).values(account_status='blocked'))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(confirm())
    assert exc.value.status_code==403


def test_open_websocket_rechecks_account_status(pg):
    from tests.integration.test_order_critical_path import ws_login
    from starlette.websockets import WebSocketDisconnect
    with pg.client.websocket_connect(f'/ws/orders/ws/staff?company_id={pg.ids["company_a"]}') as socket:
        ws_login(pg,socket,'admin_a')
        assert socket.receive_json()['type']=='ready'
        with pg.engine.begin() as conn:
            conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['admin_a']).values(account_status='blocked'))
        socket.send_json({'type':'unsupported'})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_resend_invalidates_previous_code_and_concurrent_verification(pg,monkeypatch,tmp_path):
    from auth.email_confirmation import verify_code
    from fastapi import HTTPException
    pending(pg);local_delivery(monkeypatch,tmp_path)
    monkeypatch.setattr('auth.email_confirmation.secrets.randbelow',lambda n:123456)
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==200
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_a']).values(email_code_sent_at=datetime.now(timezone.utc)-timedelta(seconds=61)))
    monkeypatch.setattr('auth.email_confirmation.secrets.randbelow',lambda n:654321)
    assert pg.client.post('/login/email/request-code',json=credentials()).status_code==200
    assert pg.client.post('/login/email/confirm',json={**credentials(),'code':'123456'}).status_code==400
    async def one():
        async with pg.sessions() as session:
            try:
                await verify_code(session,credentials()['email'],PASSWORD,'654321')
                return 200
            except HTTPException as exc:
                return exc.status_code
    async def both():
        return await asyncio.gather(one(),one())
    assert sorted(asyncio.run(both()))==[200,400]
