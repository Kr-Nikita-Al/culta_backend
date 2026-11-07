import pytest
pytestmark=pytest.mark.integration

def test_staff_table_scope_and_permissions(pg):
    params={'company_id':str(pg.ids['company_a'])}
    for role in ('admin_b','client_a','waiter_a'):
        assert pg.client.get('/user_role/staff_table',params=params,headers=pg.headers(role)).status_code==403
    response=pg.client.get('/user_role/staff_table',params=params,headers=pg.headers())
    assert response.status_code==200,response.text
    data=response.json()
    ids={u['user_id'] for u in data['users']}
    assert str(pg.ids['admin_a']) in ids and str(pg.ids['waiter_a']) in ids
    assert str(pg.ids['admin_b']) not in ids and str(pg.ids['client_a']) not in ids
    assert next(u for u in data['users'] if u['user_id']==str(pg.ids['admin_a']))['self']
    assert 'PORTAL_ROLE_OWNER' not in data['grantable_roles']
    assert 'PORTAL_ROLE_ADMIN' not in data['revocable_roles']
    assert 'PORTAL_ROLE_WAITER' in data['revocable_roles']
