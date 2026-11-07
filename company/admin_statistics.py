"""Read-only cross-company statistics, restricted to global superadmins."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, func, literal_column
from db import CompanyDB, CheckDB, OrderDB, UserRoleDB, UserDB
from db.session import get_db
from user.actions import __get_user_from_token
from utils.constants import EMPTY_UUID, PortalRole

router = APIRouter()


@router.get('/statistics')
async def statistics(date_from: date, date_to: date, response: Response, db=Depends(get_db), user=Depends(__get_user_from_token)):
    response.headers['Cache-Control'] = 'no-store'
    allowed = await db.scalar(select(UserRoleDB.relation_id).where(
        UserRoleDB.is_active.is_(True),
        UserRoleDB.user_id==user.user_id, UserRoleDB.company_id==EMPTY_UUID,
        UserRoleDB.role==PortalRole.PORTAL_ROLE_SUPER_ADMIN).limit(1))
    if allowed is None:
        raise HTTPException(403, 'Superadmin access required')
    if date_to < date_from or (date_to-date_from).days > 366 or date_to==date.max:
        raise HTTPException(422, 'Select a period of up to 367 days')
    start=datetime.combine(date_from,time.min,tzinfo=timezone.utc)
    end=datetime.combine(date_to+timedelta(days=1),time.min,tzinfo=timezone.utc)
    try:
        previous_start=start-(end-start)
    except OverflowError:
        raise HTTPException(422, 'Period is outside supported dates')
    # Aggregate checks before joining companies: multiple orders must not multiply revenue.
    checks=select(CheckDB.company_id.label('company'),func.count().label('closed_checks'),
        func.sum(CheckDB.paid_amount).label('revenue'),func.sum(CheckDB.bonus_spent).label('bonuses')).where(
        CheckDB.status=='closed',CheckDB.closed_at>=start,CheckDB.closed_at<end).group_by(CheckDB.company_id).subquery()
    orders=select(CheckDB.company_id.label('company'),func.count(OrderDB.order_id).label('orders')).join(
        OrderDB,OrderDB.check_id==CheckDB.check_id).where(CheckDB.status=='closed',
        CheckDB.closed_at>=start,CheckDB.closed_at<end).group_by(CheckDB.company_id).subquery()
    rows=(await db.execute(select(CompanyDB.company_id,CompanyDB.company_name,CompanyDB.is_active,
        checks.c.closed_checks,checks.c.revenue,checks.c.bonuses,orders.c.orders).outerjoin(
        checks,checks.c.company==CompanyDB.company_id).outerjoin(orders,orders.c.company==CompanyDB.company_id)
        .order_by(CompanyDB.company_name,CompanyDB.company_id))).all()
    companies=[]
    for row in rows:
        revenue=row.revenue or Decimal('0')
        count=row.closed_checks or 0
        companies.append(dict(company_id=row.company_id,name=row.company_name,is_active=row.is_active,
            closed_checks=count,orders=row.orders or 0,revenue=format(revenue,'.2f'),
            bonuses=format(row.bonuses or Decimal('0'),'.2f'),
            average_check=format(revenue/count if count else Decimal('0'),'.2f')))
    total=sum((Decimal(c['revenue']) for c in companies),Decimal('0'))
    count=sum(c['closed_checks'] for c in companies)
    previous=(await db.execute(select(func.count(),func.coalesce(func.sum(CheckDB.paid_amount),0)).where(
        CheckDB.status=='closed',CheckDB.closed_at>=previous_start,CheckDB.closed_at<start))).one()
    previous_total=Decimal(previous[1])
    change=total-previous_total
    day=func.date(func.timezone(literal_column("'UTC'"),CheckDB.closed_at))
    daily_rows=(await db.execute(select(day,func.count(),func.sum(CheckDB.paid_amount)).where(
        CheckDB.status=='closed',CheckDB.closed_at>=start,CheckDB.closed_at<end).group_by(day))).all()
    daily_map={row[0]:row for row in daily_rows}
    daily=[]
    for offset in range((date_to-date_from).days+1):
        date_value=date_from+timedelta(days=offset)
        row=daily_map.get(date_value)
        daily.append(dict(date=date_value,closed_checks=row[1] if row else 0,
                          revenue=format(row[2] if row else Decimal('0'),'.2f')))
    user_counts=(await db.execute(select(UserDB.account_status,func.count()).group_by(UserDB.account_status))).all()
    user_statuses=dict(user_counts)
    available=await db.scalar(select(func.count()).select_from(UserDB).where(UserDB.is_active.is_(True),UserDB.account_status=='confirmed'))
    order_filter=(OrderDB.time_created>=start,OrderDB.time_created<end)
    active_buyers=await db.scalar(select(func.count(func.distinct(OrderDB.user_id))).join(UserDB,UserDB.user_id==OrderDB.user_id).where(*order_filter))
    order_statuses=(await db.execute(select(OrderDB.status,func.count()).where(*order_filter).group_by(OrderDB.status))).all()
    activity={}
    for model,key in ((UserDB,'registrations'),(OrderDB,'orders')):
        activity_day=func.date(func.timezone(literal_column("'UTC'"),model.time_created))
        activity[key]=dict((await db.execute(select(activity_day,func.count()).where(model.time_created>=start,model.time_created<end).group_by(activity_day))).all())
    for entry in daily:
        entry.update({key:values.get(entry['date'],0) for key,values in activity.items()})
    return dict(date_from=date_from,date_to=date_to,timezone='UTC',companies=companies,
        users=dict(total=sum(user_statuses.values()),available=available,active_buyers=active_buyers,
                   new=sum(activity['registrations'].values()),statuses=user_statuses),
        order_activity=dict(total=sum(n for _,n in order_statuses),statuses={status.value:n for status,n in order_statuses}),
        daily=daily,comparison=dict(date_from=previous_start.date(),date_to=(start-timedelta(days=1)).date(),
            revenue=format(previous_total,'.2f'),closed_checks=previous[0],
            revenue_change=format(change,'.2f'),
            revenue_change_percent=format(change/previous_total*100,'.2f') if previous_total else None),
        totals=dict(companies=len(companies),closed_checks=count,orders=sum(c['orders'] for c in companies),
                    revenue=format(total,'.2f'),average_check=format(total/count if count else Decimal('0'),'.2f')))
