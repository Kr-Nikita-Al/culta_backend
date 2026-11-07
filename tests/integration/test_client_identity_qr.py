import time
from uuid import uuid4
import pytest
from jose import jwt
from sqlalchemy import update
from db import UserDB, UserRoleDB
from settings import QR_SECRET_KEY, QR_ALGORITHM
from user.actions.qr_code_action import generate_jwt_qr_data

pytestmark = pytest.mark.integration


def scan(pg,token,role='admin_a',company='company_a'):
    return pg.client.post('/user/scan_qr_code',headers=pg.headers(role),json={
        'qr_token':token,'company_id':str(pg.ids[company])})


def test_client_identity_permissions_and_status(pg):
    token=generate_jwt_qr_data(str(pg.ids['client_a']))
    assert scan(pg,token).status_code==200
    for role in ('client_a','cook_a','admin_b'):
        assert scan(pg,token,role).status_code==403
    assert scan(pg,token,'waiter_a').status_code==200
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id==pg.ids['client_a']).values(account_status='blocked'))
    assert scan(pg,token).status_code==403
    with pg.engine.begin() as conn:
        conn.execute(update(UserRoleDB).where(UserRoleDB.user_id==pg.ids['admin_a']).values(is_active=False))
    assert scan(pg,token).status_code==403


@pytest.mark.parametrize('change',[
    {'type':'qr_auth'}, {'aud':'other'}, {'exp':0}, {'user_id':'bad'}, {'user_id':123},
    {'iat':int(time.time())+100}, {'jti':None}, {'exp':int(time.time())+3600},
])
def test_invalid_qr(pg,change):
    now=int(time.time())
    data={'user_id':str(pg.ids['client_a']),'iat':now,'exp':now+300,
          'type':'client_identity','aud':'culta:client-identity','jti':str(uuid4()),**change}
    token=jwt.encode(data,QR_SECRET_KEY,algorithm=QR_ALGORITHM)
    assert scan(pg,token).status_code==401


def test_missing_client_and_fresh_image(pg):
    assert scan(pg,generate_jwt_qr_data(str(uuid4()))).status_code==404
    params={'user_id':str(pg.ids['client_a'])}
    url='/user/get_user_qr_code_by_id'
    first=pg.client.get(url,params=params,headers=pg.headers('client_a'))
    second=pg.client.get(url,params=params,headers=pg.headers('client_a'))
    assert first.status_code==second.status_code==200
    assert first.json()['qr_code']!=second.json()['qr_code']
    assert first.json()['qr_code'].startswith('data:image/png;base64,')
    assert pg.client.get(url,params=params,headers=pg.headers()).status_code==403
