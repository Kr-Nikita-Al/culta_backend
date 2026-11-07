from datetime import datetime
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db import CheckDB, OrderDB, UserDB, CompanyDB, STATUS_TYPE
from bonuses.settlement import redemption_limit
from company.infrastructure import effective_rates
from db.session import get_db
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model
from utils.base_model_response import BaseModelResponse
from utils.money import Money, MoneyResponse, MAX_MONEY
from checks.service import close_check, link_guest
from order.api_handlers import OrderRoute, _notify_order_updated
from order.order_product_association.model_dal import OrderProductAssociationDal

from company.modules import module_guard
check_router = APIRouter(route_class=OrderRoute, dependencies=[Depends(module_guard('orders'))])


class CloseCheckRequest(BaseModel):
    check_id: UUID
    company_id: UUID
    paid_amount: Money
    bonus_spent: Money = Decimal('0.00')

    class Config:
        extra = 'forbid'


class CheckResponse(BaseModelResponse):
    loyalty_level_name: Optional[str] = None
    order_context: Optional[str] = None
    table_id: Optional[UUID] = None
    check_id: UUID
    company_id: UUID
    user_id: Optional[UUID] = None
    guest_name: Optional[str] = None
    service_type: str
    status: str
    total_amount: Optional[MoneyResponse]
    paid_amount: MoneyResponse
    bonus_spent: MoneyResponse
    bonus_earned: MoneyResponse
    bonus_payment_perc: Optional[MoneyResponse]
    bonus_accrual_perc: Optional[MoneyResponse]
    bonus_balance: Optional[MoneyResponse] = None
    max_bonus_spend: Optional[MoneyResponse] = None
    closed_at: Optional[datetime]
    order_ids: List[UUID]


async def response_for(check, db, show_wallet=False):
    orders = (await db.execute(select(OrderDB).where(OrderDB.check_id == check.check_id)
                              .order_by(OrderDB.order_id))).scalars().all()
    result = CheckResponse(**{
        **{field: getattr(check, field) for field in CheckResponse.__fields__ if field not in ('order_ids', 'bonus_balance', 'max_bonus_spend')},
        'order_ids': [order.order_id for order in orders],
    })
    if check.status == 'open':
        total = Decimal('0.00')
        for order in orders:
            if order.status != STATUS_TYPE.CANCELED:
                total += await OrderProductAssociationDal(db).calculate_order_total(order.order_id)
                if total > MAX_MONEY:
                    raise HTTPException(422, 'Check total exceeds the supported amount')
        result.total_amount = total
        if show_wallet and check.user_id is not None:
            company = await db.get(CompanyDB, check.company_id)
            user = await db.get(UserDB, check.user_id)
            result.bonus_balance = user.bonus_balance if user.is_active else Decimal('0')
            payment, accrual, level, cumulative = await effective_rates(db, company, check.user_id)
            result.bonus_payment_perc = payment
            result.bonus_accrual_perc = accrual
            result.loyalty_level_name = level
            result.max_bonus_spend = redemption_limit(total, result.bonus_balance, result.bonus_payment_perc)
    return result


@check_router.get('/open', response_model=List[CheckResponse])
async def open_checks(company_id: UUID, db: AsyncSession = Depends(get_db),
                      cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(cur_user.user_id, db, company_id)
    if not (role.is_owner or role.is_admin or role.is_waiter):
        raise HTTPException(403, 'Forbidden')
    async with db.begin():
        checks = (await db.execute(select(CheckDB).where(CheckDB.company_id == company_id,
            CheckDB.status == 'open', CheckDB.service_type == 'waiter_service')
            .order_by(CheckDB.time_created.desc()).limit(100))).scalars().all()
        return [await response_for(check, db) for check in checks]


@check_router.get('/tables')
async def tables(company_id: UUID, db: AsyncSession = Depends(get_db), cur_user: UserDB = Depends(__get_user_from_token)):
    from db import DiningTableDB
    role = await __get_user_role_model(cur_user.user_id, db, company_id)
    if not (role.is_owner or role.is_admin or role.is_waiter):
        raise HTTPException(403, 'Forbidden')
    async with db.begin():
        rows = (await db.execute(select(DiningTableDB).where(DiningTableDB.company_id == company_id,
            DiningTableDB.is_active.is_(True)).order_by(DiningTableDB.label))).scalars().all()
        return [{'table_id': row.table_id, 'name': row.label} for row in rows]


@check_router.get('/clients')
async def clients(company_id: UUID, query: str = '', db: AsyncSession = Depends(get_db), cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(cur_user.user_id, db, company_id)
    if not (role.is_owner or role.is_admin or role.is_waiter):
        raise HTTPException(403, 'Forbidden')
    query = query.strip()
    if len(query) < 3 or len(query) > 150:
        return []
    async with db.begin():
        # Names are searchable only among previous clients of this establishment.
        # A new client can be located by an exact email, or identified by signed QR.
        known = select(CheckDB.user_id).where(CheckDB.company_id == company_id, CheckDB.user_id.isnot(None))
        users = (await db.execute(select(UserDB).where(UserDB.is_active.is_(True),
            UserDB.account_status == 'confirmed', or_(UserDB.email == query.lower(),
            UserDB.user_id.in_(known) & func.lower(UserDB.name + ' ' + UserDB.surname).contains(query.lower(), autoescape=True)))
            .order_by(UserDB.name, UserDB.surname, UserDB.user_id).limit(20))).scalars().all()
        return [{'user_id': user.user_id, 'name': user.name, 'surname': user.surname} for user in users]


class LinkGuestRequest(BaseModel):
    check_id: UUID
    company_id: UUID
    qr_token: str

    class Config:
        extra = 'forbid'


@check_router.post('/link_guest', response_model=CheckResponse)
async def link(body: LinkGuestRequest, db: AsyncSession = Depends(get_db),
               cur_user: UserDB = Depends(__get_user_from_token)):
    from user.actions.qr_code_action import __verify_qr_token
    role = await __get_user_role_model(cur_user.user_id, db, body.company_id)
    if not (role.is_owner or role.is_admin or role.is_waiter):
        raise HTTPException(403, 'Forbidden')
    payload = await __verify_qr_token(body.qr_token)
    async with db.begin():
        check = await link_guest(db, body.check_id, body.company_id, UUID(payload['user_id']), cur_user.user_id)
        result = await response_for(check, db, True)
    for order_id in result.order_ids:
        await _notify_order_updated(order_id, db)
    return result


@check_router.get('/get', response_model=CheckResponse)
async def get_check(check_id: UUID, company_id: UUID, db: AsyncSession = Depends(get_db),
                    cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(cur_user.user_id, db, company_id)
    async with db.begin():
        # Same lock as mutations: the displayed amount is one consistent snapshot.
        check = (await db.execute(select(CheckDB).where(CheckDB.check_id == check_id,
            CheckDB.company_id == company_id).with_for_update())).scalar_one_or_none()
        if check is None or not (role.is_owner or role.is_admin or role.is_waiter or
                                 role.is_cook or check.user_id == cur_user.user_id):
            raise HTTPException(404, 'Check not found')
        return await response_for(check, db, role.is_owner or role.is_admin or role.is_waiter or check.user_id == cur_user.user_id)


@check_router.post('/close', response_model=CheckResponse)
async def close(body: CloseCheckRequest, db: AsyncSession = Depends(get_db),
                cur_user: UserDB = Depends(__get_user_from_token)):
    role = await __get_user_role_model(cur_user.user_id, db, body.company_id)
    if not cur_user.is_active or not (role.is_owner or role.is_admin or role.is_waiter):
        raise HTTPException(403, 'Forbidden')
    async with db.begin():
        check = await close_check(db, body.check_id, body.company_id, cur_user.user_id, body.paid_amount, body.bonus_spent)
        result = await response_for(check, db)
    for order_id in result.order_ids:
        await _notify_order_updated(order_id, db)
    return result
