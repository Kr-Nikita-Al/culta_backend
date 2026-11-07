import pytest
pytestmark = pytest.mark.integration


def test_publication_roundtrip_and_ancestor_visibility(pg):
    params = {'company_id': str(pg.ids['company_a'])}
    headers = pg.headers()
    from sqlalchemy import text
    with pg.engine.begin() as conn:
        conn.execute(text('UPDATE company SET email=:email WHERE company_id=:id'), {'email':'culta@example.com','id':params['company_id']})
    def save(body):
        return pg.client.put('/navigation_editor/canvas', params=params, headers=headers, json=body)
    def read():
        return pg.client.get('/navigation_editor', params=params, headers=headers).json()
    body = {'title':'Menu','containers':[{'title':'Tea','x':12,'y':12,'items':[{'product_id':str(pg.ids['product_a']),'x':12,'y':12}]}]}
    result = save(body)
    assert result.status_code == 200, result.text
    data = read()
    sid, cid, iid = data['screens'][0]['id'], data['containers'][0]['id'], data['items'][0]['id']
    body.update(id=sid,version=1)
    body['containers'][0]['id'] = cid
    body['containers'][0]['items'][0]['id'] = iid
    def public(kind, ident):
        return pg.client.get('/'+kind+'_navigation/get_by_id', params={kind+'_id':ident})
    assert public('screen',sid).status_code == 200
    body['containers'][0]['items'][0]['is_visible'] = False
    assert save(body).status_code == 200
    assert public('item',iid).status_code == 404
    assert public('screen',sid).json()['containers'][0]['items'] == []
    assert read()['items'][0]['is_visible'] is False
    assert next(p for p in read()['products'] if p['id']==str(pg.ids['product_a']))['is_used'] is True
    # Older clients omitting flags do not make an existing placement visible again.
    body['version'] = 2
    del body['containers'][0]['items'][0]['is_visible']
    assert save(body).status_code == 200
    assert read()['items'][0]['is_visible'] is False
    body['version'] = 3
    body['containers'][0]['is_active'] = False
    assert save(body).status_code == 200
    assert public('container',cid).status_code == 404
    assert public('screen',sid).json()['containers'] == []
    body['version'] = 4
    body['is_visible'] = False
    assert save(body).status_code == 200
    assert public('screen',sid).status_code == 404
    assert public('container',cid).status_code == 404
    company = pg.client.get('/company/get_by_id', params=params)
    assert company.status_code == 200, company.text
    assert company.json()['screens'] == []
    body['version'] = 5
    body['is_visible'] = True
    body['containers'][0]['is_active'] = True
    body['containers'][0]['items'][0]['is_visible'] = True
    assert save(body).status_code == 200
    assert public('item',iid).status_code == 200
