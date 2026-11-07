from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, update
from db import CheckDB, CompanyDB, OrderDB, UserDB, STATUS_TYPE
from bonuses.settlement import settle
from db.check_model import utc_now
from order.order_product_association.model_dal import OrderProductAssociationDal
from utils.money import MAX_MONEY, CENT


async def assign_check(session, body, actor, *, client_context=None):
    if body.user_id is not None and client_context is None:
        from user.account_status import require_confirmed
        user = await session.scalar(select(UserDB).where(UserDB.user_id == body.user_id).with_for_update()
                                    .execution_options(populate_existing=True))
        if user is None:
            raise HTTPException(404, 'Client not found')
        require_confirmed(user)
    # Lock company setting against concurrent changes while choosing the mode.
    mode = (await session.execute(select(CompanyDB.service_type).where(
        CompanyDB.company_id == body.company_id).with_for_update(read=True))).scalar_one_or_none()
    if mode is None:
        raise HTTPException(404, 'Company not found')
    if body.check_id is not None:
        check = (await session.execute(select(CheckDB).where(CheckDB.check_id == body.check_id,
            CheckDB.company_id == body.company_id, CheckDB.user_id == body.user_id).with_for_update())).scalar_one_or_none()
        if check is None:
            raise HTTPException(404, 'Check not found')
        if check.status != 'open' or check.service_type != 'waiter_service' or mode != 'waiter_service':
            raise HTTPException(409, 'Only an open waiter-service check accepts another order')
        if client_context is not None and (check.order_context != client_context['order_context'] or
                                           check.table_id != client_context['table_id']):
            raise HTTPException(409, 'Check belongs to a different visit context')
        return check.check_id
    if client_context is None and body.table_id:
        from db import DiningTableDB
        table = await session.scalar(select(DiningTableDB).where(
            DiningTableDB.table_id == body.table_id, DiningTableDB.company_id == body.company_id))
        if table is None or not table.is_active:
            raise HTTPException(422, 'Table unavailable')
    check = CheckDB(company_id=body.company_id, user_id=body.user_id,
                    guest_name=(body.guest_name or None) if body.user_id is None else None,
                    service_type=mode, creator_id=actor, updater_id=actor,
                    order_context=client_context['order_context'] if client_context else ('inside' if body.table_id else None),
                    table_id=client_context['table_id'] if client_context else body.table_id)
    session.add(check)
    await session.flush()
    return check.check_id


async def close_check(session, check_id, company_id, actor, paid_amount, bonus_spent=Decimal('0.00')):
    # Wallet -> company -> check -> orders, matching client-order creation.
    initial = (await session.execute(select(CheckDB.user_id).where(CheckDB.check_id == check_id,
                                                               CheckDB.company_id == company_id))).one_or_none()
    if initial is None:
        raise HTTPException(404, 'Check not found')
    user_id = initial.user_id
    user = await session.scalar(select(UserDB).where(UserDB.user_id == user_id).with_for_update()
                                .execution_options(populate_existing=True)) if user_id else None
    company = (await session.execute(select(CompanyDB).where(CompanyDB.company_id == company_id)
        .with_for_update(read=True, of=CompanyDB).execution_options(populate_existing=True))).unique().scalar_one_or_none()
    check = (await session.execute(select(CheckDB).where(CheckDB.check_id == check_id,
        CheckDB.company_id == company_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if check is None:
        raise HTTPException(404, 'Check not found')
    if check.user_id != user_id:
        raise HTTPException(409, 'Check client changed; reload before payment')
    if check.status == 'closed':
        if check.paid_amount != paid_amount or check.bonus_spent != bonus_spent:
            raise HTTPException(409, 'Check already closed with a different payment')
        return check
    if check.status != 'open':
        raise HTTPException(409, 'Check is not open')
    if not company or not company.is_active:
        raise HTTPException(409, 'Company is inactive')
    orders = (await session.execute(select(OrderDB).where(OrderDB.check_id == check_id)
        .order_by(OrderDB.order_id).with_for_update())).scalars().all()
    if not orders:
        raise HTTPException(409, 'Empty check cannot be closed')
    if any(o.status not in (STATUS_TYPE.COMPLETED, STATUS_TYPE.CANCELED) for o in orders):
        raise HTTPException(409, 'Finish or cancel every order before closing the check')
    total = Decimal('0.00')
    for order in orders:
        if order.status == STATUS_TYPE.CANCELED:
            continue
        # Recompute from historical positions, not from a UI-supplied total.
        total += await OrderProductAssociationDal(session).calculate_order_total(order.order_id)
        if total > MAX_MONEY:
            raise HTTPException(422, 'Check total exceeds the supported amount')
    total = total.quantize(CENT)
    if user_id is None:
        if bonus_spent != 0 or paid_amount != total:
            raise HTTPException(409, 'Guest checks must be paid entirely with money')
        check.bonus_spent = check.bonus_earned = Decimal('0.00')
        check.bonus_payment_perc = check.bonus_accrual_perc = Decimal('0.00')
    else:
        await settle(session, check, user, company, total, paid_amount, bonus_spent, actor)
    check.total_amount = total
    check.paid_amount = paid_amount
    check.status = 'closed'
    check.closed_at = utc_now()
    check.updater_id = actor
    await session.flush()
    return check


async def link_guest(session, check_id, company_id, user_id, actor):
    from user.account_status import require_confirmed
    user = await session.scalar(select(UserDB).where(UserDB.user_id == user_id).with_for_update()
                                .execution_options(populate_existing=True))
    if user is None:
        raise HTTPException(404, 'Client not found')
    require_confirmed(user)
    company = await session.scalar(select(CompanyDB).where(CompanyDB.company_id == company_id).with_for_update(read=True, of=CompanyDB))
    if company is None or not company.is_active:
        raise HTTPException(409, 'Company is inactive')
    check = await session.scalar(select(CheckDB).where(CheckDB.check_id == check_id,
        CheckDB.company_id == company_id).with_for_update().execution_options(populate_existing=True))
    if check is None:
        raise HTTPException(404, 'Check not found')
    if check.status != 'open' or check.user_id not in (None, user_id):
        raise HTTPException(409, 'Only an open guest check can be linked')
    check.user_id = user_id
    check.updater_id = actor
    await session.execute(update(OrderDB).where(OrderDB.check_id == check_id).values(user_id=user_id, updater_id=actor))
    await session.flush()
    return check
