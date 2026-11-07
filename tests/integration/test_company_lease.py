from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import text
pytestmark=pytest.mark.integration

def test_company_lease_scope_renew_expiry_and_release(pg):
    company=str(pg.ids['company_a'])
    params={'company_id':company}
    def call(method,token=None,role='admin_a'):
        headers=pg.headers(role)
        if token:headers['X-Company-Edit-Token']=token
        return getattr(pg.client,method)('/company/edit-lease',params=params,headers=headers)
    assert call('post',role='client_a').status_code==403
    assert call('post',role='admin_b').status_code==403
    first=call('post');assert first.status_code==200,first.text
    token=first.json()['token']
    assert call('post').status_code==423
    assert call('put',str(uuid4())).status_code==423
    assert call('put',token).status_code==200
    def patch(token=None):
        headers=pg.headers()
        if token:headers['X-Company-Edit-Token']=token
        return pg.client.patch('/company/update_by_id',params=params,headers=headers,json={'company_name':'Updated'})
    assert patch().status_code==423
    assert patch(token).status_code==200
    settings=pg.client.get('/company/infrastructure',params=params,headers=pg.headers()).json()
    assert pg.client.put('/company/infrastructure',params=params,headers=pg.headers(),json=settings).status_code==423
    assert pg.client.put('/photos/company',params=params,headers=pg.headers(),json={'image_id':str(uuid4())}).status_code==423
    # A stale release must not clear another editor's lease.
    assert call('delete',str(uuid4())).status_code==200
    assert call('post').status_code==423
    with pg.engine.begin() as c:
        c.execute(text("UPDATE company SET edit_lease_expires_at=now()-interval '1 second' WHERE company_id=:id"),{'id':company})
    assert patch(token).status_code==423
    assert call('put',token).status_code==423
    second=call('post').json()['token']
    assert second!=token
    assert call('delete',token).status_code==200
    assert patch(second).status_code==200
    assert call('delete',second).status_code==200
    assert call('post').status_code==200

def test_concurrent_lease_acquisition(pg):
    params={'company_id':str(pg.ids['company_a'])}
    headers=pg.headers()
    def acquire(_):
        return pg.client.post('/company/edit-lease',params=params,headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(acquire,range(2)))
    assert sorted(r.status_code for r in results)==[200,423]
