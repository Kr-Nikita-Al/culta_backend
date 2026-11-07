import pytest
from sqlalchemy import update
from db import UserDB, UserRoleDB

pytestmark = pytest.mark.integration


def search(pg, actor='admin_a', **params):
    return pg.client.get('/user_role/search_staff_candidates', headers=pg.headers(actor), params={
        'company_id': str(pg.ids['company_a']), 'role': 'PORTAL_ROLE_WAITER',
        'action': 'grant', 'q': 'Test', **params})


def test_search_names_and_privacy(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id == pg.ids['client_a']).values(name='Никита', surname='Иванов'))
    result = search(pg, q='  Иванов ник  ')
    assert result.status_code == 200
    users = result.json()['users']
    assert len(users) == 1
    assert users[0]['user_id'] == str(pg.ids['client_a'])
    assert set(users[0]) == {'user_id', 'name', 'surname', 'email_hint'}
    assert users[0]['email_hint'] == 'c***@example.test'
    assert search(pg, q='%%').json()['users'] == []
    assert search(pg, q=' ').status_code == 422
    assert search(pg, q='x' * 101).status_code == 422


def test_search_permissions_and_revocation_scope(pg):
    for actor in ('client_a', 'waiter_a', 'cook_a', 'admin_b'):
        assert search(pg, actor).status_code == 403
    assert search(pg, role='PORTAL_ROLE_OWNER').status_code == 403
    users = search(pg, action='revoke').json()['users']
    assert [u['user_id'] for u in users] == [str(pg.ids['waiter_a'])]
    with pg.engine.begin() as conn:
        conn.execute(update(UserRoleDB).where(UserRoleDB.user_id == pg.ids['admin_a']).values(is_active=False))
    assert search(pg).status_code == 403


def test_search_status_and_grant_flow(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(UserDB).where(UserDB.user_id == pg.ids['client_b']).values(account_status='pending'))
    users = search(pg).json()['users']
    assert str(pg.ids['client_b']) not in [u['user_id'] for u in users]
    assert str(pg.ids['admin_a']) not in [u['user_id'] for u in users]
    target = next(u['user_id'] for u in users if u['user_id'] == str(pg.ids['client_a']))
    params = {'company_id': str(pg.ids['company_a']), 'role': 'PORTAL_ROLE_WAITER'}
    assert pg.client.post('/user_role/grant_staff_privilege', headers=pg.headers(), params={
        **params, 'promo_user_id': str(pg.ids['client_b'])}).status_code == 403
    grant = pg.client.post('/user_role/grant_staff_privilege', headers=pg.headers(), params={**params, 'promo_user_id': target})
    assert grant.status_code == 200, grant.text
    assert target in [u['user_id'] for u in search(pg, action='revoke').json()['users']]
    revoke = pg.client.delete('/user_role/revoke_staff_privilege', headers=pg.headers(), params={**params, 'demo_user_id': target})
    assert revoke.status_code == 200, revoke.text
