import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db import UserRoleDB, CheckDB, OrderDB
from utils.constants import EMPTY_UUID
pytestmark=pytest.mark.integration


def test_statistics_access_period_and_revenue(pg):
    params={'date_from':'2026-01-01','date_to':'2026-01-31'}
    assert pg.client.get('/admin/statistics',params=params,headers=pg.headers()).status_code==403
    with Session(pg.engine) as session,session.begin():
        session.add(UserRoleDB(user_id=pg.ids['admin_a'],company_id=EMPTY_UUID,role='PORTAL_ROLE_SUPER_ADMIN'))
        for month,total,paid in [(1,100,80),(2,200,200)]:
            check=CheckDB(company_id=pg.ids['company_a'],user_id=pg.ids['client_a'],creator_id=pg.ids['admin_a'],updater_id=pg.ids['admin_a'],status='closed',closed_at=datetime(2026,month,1,tzinfo=timezone.utc),total_amount=total,paid_amount=paid,bonus_spent=total-paid)
            session.add(check)
            session.flush()
            for _ in range(2):
                session.add(OrderDB(check_id=check.check_id,company_id=check.company_id,user_id=check.user_id,staff_id=pg.ids['admin_a'],time_created=datetime(2026,month,1,tzinfo=timezone.utc)))
    response=pg.client.get('/admin/statistics',params=params,headers=pg.headers())
    assert response.status_code==200,response.text
    result=response.json()
    assert result['totals']['revenue']=='80.00'
    assert result['totals']['closed_checks']==1
    assert result['totals']['orders']==2
    assert result['order_activity']['total']==2
    assert result['order_activity']['statuses']=={'created':2}
    assert result['users']['active_buyers']==1
    assert result['users']['total']==6
    assert result['users']['available']==6
    assert result['daily'][0]['orders']==2
    assert result['daily'][1]['orders']==0
    assert result['comparison']['date_from']=='2025-12-01'
    assert result['comparison']['date_to']=='2025-12-31'
    assert result['comparison']['revenue_change_percent'] is None
    assert len(result['daily'])==31
    assert result['daily'][0]['revenue']=='80.00'
    assert result['daily'][1]['revenue']=='0.00'
    assert len(result['companies'])==2
    assert next(c for c in result['companies'] if c['company_id']==str(pg.ids['company_b']))['revenue']=='0.00'
    assert pg.client.get('/admin/statistics',params={'date_from':'2026-02-01','date_to':'2026-01-01'},headers=pg.headers()).status_code==422
    assert pg.client.get('/admin/statistics',params=params,headers=pg.headers('admin_b')).status_code==403
