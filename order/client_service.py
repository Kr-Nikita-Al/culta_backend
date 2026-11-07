"""Client identity, revocable opaque table tokens and retry protection."""
import hashlib
import hmac
import json
import secrets
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from db import CompanyDB, DiningTableDB, OrderDB, UserDB
from reservations.service import permissions


async def active_actor(session, user_id, lock=False):
    query = select(UserDB.user_id).where(UserDB.user_id == user_id, UserDB.is_active.is_(True))
    if lock:
        query = query.with_for_update()
    if (await session.execute(query)).scalar_one_or_none() is None:
        raise HTTPException(403, 'Inactive user')


async def active_company(session, company_id):
    row = (await session.execute(select(CompanyDB).where(CompanyDB.company_id == company_id,
        CompanyDB.is_active.is_(True)).with_for_update(read=True, of=CompanyDB))).unique().scalar_one_or_none()
    if row is None:
        raise HTTPException(404, 'Company not found')
    return row


async def resolve_table(session, company_id, token):
    try:
        table_id = UUID(token.split('.', 1)[0])
    except (ValueError, AttributeError):
        raise HTTPException(403, 'Invalid or revoked table QR')
    row = (await session.execute(select(DiningTableDB).where(
        DiningTableDB.table_id == table_id, DiningTableDB.company_id == company_id,
        DiningTableDB.is_active.is_(True)).with_for_update(read=True))).scalar_one_or_none()
    digest = hashlib.sha256(token.encode()).hexdigest()
    if row is None or not row.order_qr_hash or not hmac.compare_digest(row.order_qr_hash, digest):
        raise HTTPException(403, 'Invalid or revoked table QR')
    return row


async def issue_table_qr(session, body, actor):
    await active_actor(session, actor.user_id)
    await active_company(session, body.company_id)
    can_edit, _ = await permissions(session, actor.user_id, body.company_id)
    if not can_edit:
        raise HTTPException(403, 'Only owner, admin or hostess can issue table QR')
    table = (await session.execute(select(DiningTableDB).where(
        DiningTableDB.table_id == body.table_id, DiningTableDB.company_id == body.company_id,
        DiningTableDB.is_active.is_(True)).with_for_update())).scalar_one_or_none()
    if table is None:
        raise HTTPException(404, 'Table not found')
    token = f'{table.table_id}.{secrets.token_urlsafe(32)}'
    table.order_qr_hash = hashlib.sha256(token.encode()).hexdigest()
    await session.flush()
    # Store only the digest. Each issue revokes the previous printed QR.
    return {'company_id': body.company_id, 'table_id': table.table_id, 'table_label': table.label,
            'table_token': token, 'qr_payload': f'culta://table?company_id={body.company_id}&token={token}'}


async def prepare_client_order(session, body, user_id):
    # Serialize duplicate request IDs even when no order row exists yet.
    await active_actor(session, user_id, lock=True)
    digest = hashlib.sha256(json.dumps(json.loads(body.json()), sort_keys=True,
                                      separators=(',', ':')).encode()).hexdigest()
    previous = (await session.execute(select(OrderDB).where(OrderDB.user_id == user_id,
        OrderDB.client_request_id == body.request_id))).scalar_one_or_none()
    if previous is not None:
        if previous.client_request_hash != digest:
            raise HTTPException(409, 'Request ID already used with a different order')
        return previous, None
    company = await active_company(session, body.company_id)
    if not company.work_state:
        raise HTTPException(403, 'Company is not accepting orders')
    allowed = company.allow_client_orders_inside if body.context == 'inside' else company.allow_client_orders_outside
    if not allowed:
        raise HTTPException(403, 'Client orders are disabled for this context')
    table = await resolve_table(session, body.company_id, body.table_token) if body.context == 'inside' else None
    return None, {'order_context': body.context, 'table_id': table.table_id if table else None,
                  'client_request_id': body.request_id, 'client_request_hash': digest}
