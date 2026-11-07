"""Cost visibility is a server decision scoped to the resource company."""
import pytest
from sqlalchemy import text
from test_order_critical_path import create

pytestmark = pytest.mark.integration

@pytest.mark.parametrize('role,active,allowed',[('PORTAL_ROLE_OWNER',True,True),('PORTAL_ROLE_MODERATOR',True,False),('PORTAL_ROLE_ADMIN',False,False),('PORTAL_ROLE_SUPER_ADMIN',True,False)])
def test_financial_roles_must_be_active_and_company_scoped(pg,role,active,allowed):
    with pg.engine.begin() as connection:
        connection.execute(text('UPDATE user_role SET role=:role,is_active=:active WHERE user_id=:uid'),{'role':role,'active':active,'uid':pg.ids['admin_a']})
    response=pg.client.get('/product_card/get_by_id',params={'company_id':str(pg.ids['company_a']),'product_card_id':str(pg.ids['product_a'])},headers=pg.headers())
    assert response.status_code==200,response.text
    assert ('cost_price' in response.text)==allowed

@pytest.mark.parametrize('role,allowed',[('admin_a',True),('waiter_a',False),('cook_a',False),('client_a',False),('admin_b',False)])
def test_product_cost_visibility(pg,role,allowed):
    params={'company_id':str(pg.ids['company_a']),'include_cost':'true'}
    for path,extra in [('/product_card/get_by_id',{'product_card_id':str(pg.ids['product_a'])}),('/product_card/get_product_cards_company_by_id',{})]:
        response=pg.client.get(path,params={**params,**extra},headers=pg.headers(role))
        assert response.status_code==200,response.text
        assert ('cost_price' in response.text)==allowed
        hidden=pg.client.get(path,params={**params,**extra,'include_cost':'false'},headers=pg.headers(role))
        assert hidden.status_code==200
        assert 'cost_price' not in hidden.text

def test_product_company_spoof_is_rejected(pg):
    response=pg.client.get('/product_card/get_by_id',params={'company_id':str(pg.ids['company_a']),'product_card_id':str(pg.ids['product_b'])},headers=pg.headers())
    assert response.status_code==403

@pytest.mark.parametrize('role,allowed',[('admin_a',True),('waiter_a',False),('cook_a',False),('client_a',False)])
def test_order_cost_visibility(pg,role,allowed):
    oid=create(pg).json()['order_id']
    params={} if role=='client_a' else {'company_id':str(pg.ids['company_a'])}
    for path,extra in [('/order/get_by_id',{'order_id':oid}),('/order/get_all',{})]:
        response=pg.client.get(path,params={**params,**extra},headers=pg.headers(role))
        assert response.status_code==200,response.text
        assert ('cost_price' in response.text)==allowed
        hidden=pg.client.get(path,params={**params,**extra,'include_cost':'false'},headers=pg.headers(role))
        assert hidden.status_code==200
        assert 'cost_price' not in hidden.text
