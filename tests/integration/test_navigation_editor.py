import pytest
from uuid import uuid4
pytestmark = pytest.mark.integration

def test_editor_roundtrip_and_scope(pg):
    params={'company_id':str(pg.ids['company_a'])}
    def put(kind, body, role='admin_a'):
        return pg.client.put('/navigation_editor/'+kind,params=params,headers=pg.headers(role),json=body)
    body={'title':'Сезонное меню','description':'Описание '*100,'order':0}
    assert put('screens',body,'client_a').status_code==403
    assert put('screens',body,'admin_b').status_code==403
    screen=put('screens',body)
    assert screen.status_code==200,screen.text
    sid=screen.json()['id']
    assert put('screens',body).status_code==409
    container=put('containers',{**body,'parent_id':sid})
    assert container.status_code==200,container.text
    cid=container.json()['id']
    item={'title':'Сенча','description':'Зелёный чай '*60,'price':'300.50','container_id':cid,'row':0,'column':0}
    assert put('items',{**item,'product_id':str(pg.ids['product_b'])}).status_code==404
    assert put('items',{**item,'image_id':str(uuid4())}).status_code==404
    result=put('items',item)
    assert result.status_code==200,result.text
    assert put('items',item).status_code==409
    data=pg.client.get('/navigation_editor',params=params,headers=pg.headers()).json()
    p=next(p for p in data['products'] if p['title']=='Сенча')
    assert p['price']=='300.50'
    assert p['description']==item['description']
    assert put('items',{**item,'id':result.json()['id'],'product_id':p['id'],'product_version':p['version'],'title':'Новая Сенча'}).status_code==200
    assert put('containers',{**body,'id':cid,'parent_id':sid,'title':'Чаи'}).status_code==200
    assert put('screens',{**body,'id':sid,'title':'Новое меню'}).status_code==200


def test_canvas_atomic_roundtrip_archive_and_scope(pg):
    params={'company_id':str(pg.ids['company_a'])}
    def put(kind, body, role='admin_a'):
        return pg.client.put('/navigation_editor/'+kind, params=params, headers=pg.headers(role), json=body)
    def read():
        return pg.client.get('/navigation_editor',params=params,headers=pg.headers()).json()
    product={'title':'Чай','price':'123.45','description':'Описание','proteins':5,'cost_price':'80.10'}
    assert put('products',product,'client_a').status_code==403
    assert put('products',{**product,'image_product_id':str(uuid4())}).status_code==404
    assert put('products',{**product,'id':str(pg.ids['product_b'])}).status_code==404
    result=put('products',product)
    assert result.status_code==200,result.text
    pid=result.json()['id']
    data=read()
    assert next(p for p in data['products'] if p['id']==pid)['cost_price']=='80.10'
    assert next(p for p in data['products'] if p['id']==pid)['is_used'] is False
    draft={'title':'Летнее меню','containers':[{'title':'Чаи','x':20,'y':120,'items':[{'product_id':pid,'x':30,'y':80}]}]}
    assert put('canvas',draft,'admin_b').status_code==403
    invalid={**draft,'containers':[{'title':'Чаи','x':0,'y':0,'items':[{'product_id':str(pg.ids['product_b']),'x':0,'y':0}]}]}
    assert put('canvas',invalid).status_code==404
    assert not read()['screens']
    result=put('canvas',draft)
    assert result.status_code==200,result.text
    sid=result.json()['id']
    data=read(); c=data['containers'][0]; i=data['items'][0]
    assert next(p for p in data['products'] if p['id']==pid)['is_used'] is True
    assert (c['x'],c['y'],i['x'],i['y'])==(20,120,30,80)
    updated={**draft,'id':sid,'version':1,'containers':[{'id':c['id'],'title':'Чаи','x':40,'y':200,'items':[{'id':i['id'],'product_id':pid,'x':100,'y':300}]}]}
    assert put('canvas',updated).status_code==200
    assert put('canvas',updated).status_code==409
    data=read();assert data['items'][0]['x']==100
    # Removing a placement keeps the catalog product.
    assert put('canvas',{**updated,'version':2,'containers':[]}).status_code==200
    data=read();assert not data['items'] and not data['containers']
    assert next(p for p in data['products'] if p['id']==pid)['is_used'] is False
    assert any(p['id']==pid for p in data['products'])
    assert put('canvas',draft).status_code==200
    response=pg.client.delete('/navigation_editor/products/'+pid,params=params,headers=pg.headers())
    assert response.status_code==200
    assert not any(p['id']==pid for p in read()['products'])
    assert not read()['items']
    from sqlalchemy import text
    with pg.engine.connect() as conn:
        assert conn.execute(text('SELECT is_active FROM product_card WHERE product_card_id=:id'),{'id':pid}).scalar() is False


def test_two_column_grid_validation(pg):
    params={'company_id':str(pg.ids['company_a'])}
    pid=str(pg.ids['product_a'])
    body={'title':'Grid','grid':True,'containers':[{'title':'Tea','x':12,'y':12,'items':[
        {'product_id':pid,'x':12,'y':12},{'product_id':pid,'x':164,'y':12}]}]}
    def save():
        return pg.client.put('/navigation_editor/canvas',params=params,headers=pg.headers(),json=body)
    assert save().status_code==200
    data=pg.client.get('/navigation_editor',params=params,headers=pg.headers()).json()
    assert sorted((i['row'],i['column']) for i in data['items'])==[(0,0),(0,1)]
    body['containers'][0]['items'][1]['x']=12
    assert save().status_code==422
    body['containers'][0]['items'][1]['x']=220
    assert save().status_code==422
    body['containers'][0]['items'][1].update(x=164,y=468)
    assert save().status_code==200
