import pytest
from auth import password_change as change
from tests.integration.conftest import PASSWORD
pytestmark=pytest.mark.integration

def test_password_change_requires_old_password_and_single_use_code(pg,monkeypatch):
    codes=[]
    monkeypatch.setenv('EMAIL_DELIVERY_MODE','smtp')
    monkeypatch.setattr(change,'deliver_smtp',lambda email,code,purpose:codes.append(code))
    body={'identifier':'client_a@example.test','old_password':PASSWORD,'new_password':'new-test-password'}
    def post(path,data):return pg.client.post('/login/password/'+path,json=data)
    assert post('request-code',{**body,'old_password':'incorrect'}).status_code==401
    assert not codes
    assert post('request-code',body).status_code==200
    assert post('request-code',body).status_code==429
    wrong='000000' if codes[0]!='000000' else '111111'
    assert post('confirm',{**body,'code':wrong}).status_code==400
    assert post('confirm',{**body,'code':codes[0],'new_password':'substituted-password'}).status_code==400
    assert post('confirm',{**body,'code':codes[0]}).status_code==200
    assert post('confirm',{**body,'code':codes[0]}).status_code==401
    assert pg.client.post('/login/token',data={'username':body['identifier'],'password':body['new_password']}).status_code==200
    assert pg.client.post('/login/token',data={'username':body['identifier'],'password':PASSWORD}).status_code==401
