from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import text
pytestmark = pytest.mark.integration


def test_product_versions_across_editor_and_rest(pg):
    pid=str(pg.ids['product_a'])
    company=str(pg.ids['company_a'])
    def patch(body, role='admin_a'):
        return pg.client.patch('/product_card/update_by_id', params={'product_card_id':pid}, headers=pg.headers(role), json=body)
    def editor(body):
        return pg.client.put('/navigation_editor/products', params={'company_id':company}, headers=pg.headers(), json={'id':pid,'title':'Editor',**body})
    assert patch({'title':'No version'}).status_code==428
    assert editor({}).status_code==428
    assert patch({'title':'Forbidden','version':1},'admin_b').status_code==403
    result=patch({'title':'First','version':1})
    assert result.status_code==200,result.text
    assert result.json()['version']==2
    assert editor({'version':1}).status_code==409
    assert editor({'version':2}).json()['version']==3
    assert patch({'title':'Stale','version':2}).status_code==409
    result=pg.client.get('/product_card/get_by_id',params={'product_card_id':pid,'company_id':company},headers=pg.headers())
    assert result.json()['version']==3
    assert result.json()['title']=='Editor'
    assert patch({'title':'Invalid','version':True}).status_code==422
    assert patch({'title':'Invalid','version':0}).status_code==422


def test_concurrent_product_updates_have_one_winner(pg):
    pid=str(pg.ids['product_a'])
    headers=pg.headers()
    def update(title):
        return pg.client.patch('/product_card/update_by_id',params={'product_card_id':pid},headers=headers,json={'title':title,'version':1})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(update,['First writer','Second writer']))
    assert sorted(r.status_code for r in results)==[200,409]
    with pg.engine.connect() as connection:
        row=connection.execute(text('SELECT title, version FROM product_card WHERE product_card_id=:id'),{'id':pid}).one()
    assert row.version==2
    assert row.title==(['First writer','Second writer'][next(i for i,r in enumerate(results) if r.status_code==200)])
