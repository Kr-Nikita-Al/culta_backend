from uuid import uuid4
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select
from db import ImageDB, UserRoleDB, CompanyDB
from image import photo_api
from types import SimpleNamespace
from unittest.mock import AsyncMock
from utils.constants import EMPTY_UUID

pytestmark = pytest.mark.integration


def test_company_and_role_photos_are_scoped_and_persistent(pg, monkeypatch):
    monkeypatch.setattr(photo_api, 'S3Client', lambda:SimpleNamespace(generate_get_presigned_url=AsyncMock(return_value='https://example.test/photo.jpg')))
    a,b,hidden=uuid4(),uuid4(),uuid4()
    with Session(pg.engine) as session, session.begin():
        for image_id,company,is_hidden in [(a,'company_a',False),(b,'company_b',False),(hidden,'company_a',True)]:
            session.add(ImageDB(image_id=image_id,company_id=pg.ids[company],file_name='test.jpg',is_hidden=is_hidden))
        session.add(UserRoleDB(user_id=pg.ids['admin_a'],company_id=pg.ids['company_a'],role='PORTAL_ROLE_COOK'))
    params={'company_id':str(pg.ids['company_a'])}
    def put(path,image_id,role='admin_a',extra=None):
        return pg.client.put('/photos/'+path,params={**params,**(extra or {})},json={'image_id':str(image_id)},headers=pg.headers(role))
    assert pg.client.get('/photos/options',params=params,headers=pg.headers('client_a')).status_code == 403
    options=pg.client.get('/photos/options',params=params,headers=pg.headers('waiter_a')).json()
    assert [row['image_id'] for row in options] == [str(a)]
    for bad in (b,hidden,uuid4()):
        assert put('company',bad).status_code == 422
        assert put('my-role',bad,extra={'role':'PORTAL_ROLE_ADMIN'}).status_code == 422
    assert put('company',a,'waiter_a').status_code == 403
    assert put('company',a).status_code == 200
    public=pg.client.get('/photos/company',params=params)
    assert public.status_code == 200 and public.json()['image_id'] == str(a)
    assert set(public.json()) == {'image_id','url'}
    assert put('my-role',a,extra={'role':'PORTAL_ROLE_ADMIN'}).status_code == 200
    assert put('my-role',a,'admin_b',{'role':'PORTAL_ROLE_ADMIN'}).status_code == 403
    assert put('my-role',a,extra={'role':'PORTAL_ROLE_OWNER'}).status_code == 403
    photos=pg.client.get('/photos/my-roles',params=params,headers=pg.headers()).json()
    assert {row['role']:row['image_id'] for row in photos} == {'PORTAL_ROLE_ADMIN':str(a),'PORTAL_ROLE_COOK':None}
    with Session(pg.engine) as session:
        assert session.execute(select(CompanyDB.image_picture_id).where(CompanyDB.company_id==pg.ids['company_a'])).scalar_one() == a
        assert session.execute(select(UserRoleDB.avatar_id).where(UserRoleDB.user_id==pg.ids['admin_a'],UserRoleDB.role=='PORTAL_ROLE_ADMIN')).scalar_one() == a
    assert put('my-role',EMPTY_UUID,extra={'role':'PORTAL_ROLE_ADMIN'}).status_code == 200
    assert put('company',EMPTY_UUID).status_code == 200
    assert pg.client.get('/photos/company',params=params).json()['image_id'] is None


def test_default_avatar_preserves_overrides_and_is_controlled_by_source(pg, monkeypatch):
    monkeypatch.setattr(photo_api, 'S3Client', lambda:SimpleNamespace(generate_get_presigned_url=AsyncMock(return_value='https://example.test/photo.jpg')))
    first,second=uuid4(),uuid4()
    with Session(pg.engine) as session, session.begin():
        for image_id in (first,second):
            session.add(ImageDB(image_id=image_id,company_id=pg.ids['company_a'],file_name='test.jpg'))
        for role in ('PORTAL_ROLE_COOK','PORTAL_ROLE_HOSTESS'):
            session.add(UserRoleDB(user_id=pg.ids['admin_a'],company_id=pg.ids['company_a'],role=role))
    params={'company_id':str(pg.ids['company_a'])}
    def save(role,body):
        return pg.client.put('/photos/my-role',params={**params,'role':'PORTAL_ROLE_'+role},json=body,headers=pg.headers())
    def photos():
        return {r['role'].replace('PORTAL_ROLE_',''):r for r in pg.client.get('/photos/my-roles',params=params,headers=pg.headers()).json()}
    assert save('ADMIN',{'apply_to_all':True}).status_code==422
    assert save('COOK',{'image_id':str(second)}).status_code==200
    assert save('ADMIN',{'image_id':str(first),'apply_to_all':True}).status_code==200
    values=photos()
    assert values['HOSTESS']['image_id']==str(first) and values['HOSTESS']['inherited']
    assert values['COOK']['image_id']==str(second) and not values['COOK']['inherited']
    for toggle in (True,False):
        assert save('COOK',{'apply_to_all':toggle}).status_code==409
    assert save('ADMIN',{'image_id':str(second)}).status_code==200
    assert photos()['HOSTESS']['image_id']==str(second)
    assert save('ADMIN',{'apply_to_all':False}).status_code==200
    assert photos()['HOSTESS']['image_id'] is None
    assert photos()['COOK']['image_id']==str(second)
    assert save('COOK',{'apply_to_all':True}).status_code==200
    assert save('COOK',{'image_id':str(EMPTY_UUID)}).status_code==200
    assert all(not r['default_role'] for r in photos().values())
