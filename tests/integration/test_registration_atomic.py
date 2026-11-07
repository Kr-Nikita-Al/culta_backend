import pytest
from sqlalchemy import select, func
from db import UserDB, UserRoleDB, BonusTransactionDB
from user_role.model_dal import UserRoleDAL

pytestmark=pytest.mark.integration
BODY={'name':'Test','surname':'User','phone':'89999999999','email':'atomic@example.com','password':'registration-test-password'}


def test_registration_never_requires_s3(pg,monkeypatch):
    def unavailable(*args,**kwargs):
        raise AssertionError('Registration must not access S3')
    monkeypatch.setattr('s3_directory.storage.s3client.S3Client.__init__',unavailable)
    response=pg.client.post('/user/create',json=BODY)
    assert response.status_code==200,response.text
    with pg.engine.connect() as conn:
        user=conn.execute(select(UserDB.__table__).where(UserDB.email==BODY['email'])).mappings().one()
        assert user['account_status']=='pending'
        assert user['qr_code']
        assert conn.scalar(select(func.count()).select_from(UserRoleDB).where(UserRoleDB.user_id==user['user_id']))==1
        assert conn.scalar(select(func.count()).select_from(BonusTransactionDB).where(BonusTransactionDB.user_id==user['user_id']))==1
    assert pg.client.post('/user/create',json=BODY).status_code!=200


@pytest.mark.parametrize('failure',['role','qr'])
def test_failed_registration_rolls_back_and_can_retry(pg,monkeypatch,failure):
    with pg.engine.connect() as conn:
        before=conn.scalar(select(func.count()).select_from(BonusTransactionDB))
    def fail(*args,**kwargs): raise RuntimeError('injected registration failure')
    async def async_fail(*args,**kwargs): fail()
    with monkeypatch.context() as patch:
        if failure=='role': patch.setattr(UserRoleDAL,'grant_user_role',async_fail)
        else: patch.setattr('user.actions.create_user_action.__generate_qr_base64',fail)
        with pytest.raises(RuntimeError,match='injected registration failure'):
            pg.client.post('/user/create',json=BODY)
    with pg.engine.connect() as conn:
        assert conn.scalar(select(UserDB.user_id).where(UserDB.email==BODY['email'])) is None
        assert conn.scalar(select(func.count()).select_from(BonusTransactionDB))==before
    assert pg.client.post('/user/create',json=BODY).status_code==200
