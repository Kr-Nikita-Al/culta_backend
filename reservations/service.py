from datetime import timedelta
import json
from fastapi import HTTPException
from sqlalchemy import select
from db import CompanyDB, UserRoleDB, FloorPlanDB, DiningTableDB, ReservationDB
from db.check_model import utc_now
from reservations.schemas import Table, BookingResponse, Occupancy, BoardResponse

EDIT_ROLES = {'PORTAL_ROLE_OWNER', 'PORTAL_ROLE_ADMIN', 'PORTAL_ROLE_HOSTESS'}
MANAGE_ROLES = EDIT_ROLES | {'PORTAL_ROLE_WAITER'}
ACTIVE = ('confirmed', 'seated')


async def lock_company(db, company_id, read=False):
    # Every write in this module locks the same parent before checking availability.
    # This also serializes a first layout save and concurrent booking requests.
    row = (await db.execute(select(CompanyDB.company_id).where(
        CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True))
        .with_for_update(read=read))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, 'Company not found')


async def permissions(db, user_id, company_id):
    roles = set((await db.execute(select(UserRoleDB.role).where(
        UserRoleDB.user_id == user_id, UserRoleDB.company_id == company_id,
        UserRoleDB.is_active.is_(True)))).scalars().all())
    return bool(roles & EDIT_ROLES), bool(roles & MANAGE_ROLES)


async def board(db, company_id, starts_at, ends_at, actor):
    if starts_at.tzinfo is None or ends_at.tzinfo is None or not timedelta(0) < ends_at-starts_at <= timedelta(days=31):
        raise HTTPException(422, 'Select a timezone-aware interval of at most 31 days')
    await lock_company(db, company_id, read=True)
    edit, manage = await permissions(db, actor.user_id, company_id)
    plan = await db.get(FloorPlanDB, company_id)
    tables = (await db.execute(select(DiningTableDB).where(DiningTableDB.company_id == company_id,
        DiningTableDB.is_active.is_(True)).order_by(DiningTableDB.label))).scalars().all()
    bookings = (await db.execute(select(ReservationDB).where(ReservationDB.company_id == company_id,
        ReservationDB.starts_at < ends_at, ReservationDB.ends_at > starts_at)
        .order_by(ReservationDB.starts_at, ReservationDB.reservation_id))).scalars().all()
    return BoardResponse(version=plan.version if plan else 0, tables=[Table.from_orm(t) for t in tables],
        width=plan.width if plan else 1000, height=plan.height if plan else 600,
        rooms=plan.rooms if plan else [],
        bookings=[BookingResponse.from_orm(b) for b in bookings if manage or b.user_id == actor.user_id],
        occupancy=[Occupancy.from_orm(b) for b in bookings if b.status in ACTIVE],
        can_edit_plan=edit, can_manage_bookings=manage, server_time=utc_now())


async def save_layout(db, body, actor):
    await lock_company(db, body.company_id)
    edit, _ = await permissions(db, actor.user_id, body.company_id)
    if not edit:
        raise HTTPException(403, 'Only owner, admin or hostess can edit the floor plan')
    plan = await db.get(FloorPlanDB, body.company_id)
    if body.version != (plan.version if plan else 0):
        raise HTTPException(409, 'Floor plan changed; reload before saving')
    width = body.width if body.width is not None else (plan.width if plan else 1000)
    height = body.height if body.height is not None else (plan.height if plan else 600)
    rooms = [json.loads(room.json()) for room in body.rooms] if body.rooms is not None else (plan.rooms if plan else [])
    if any(t.x + t.width/2 + 20 > width or t.y + t.height/2 + 20 > height for t in body.tables) or any(
            r['x'] + r['width'] > width or r['y'] + r['height'] > height for r in rooms):
        raise HTTPException(422, 'Floor plan must contain all tables and rooms')
    if plan is None:
        plan = FloorPlanDB(company_id=body.company_id, version=0)
        db.add(plan)
    previous = {t.table_id: t for t in (await db.execute(select(DiningTableDB).where(
        DiningTableDB.company_id == body.company_id))).scalars().all()}
    incoming = {t.table_id: t for t in body.tables}
    bookings = (await db.execute(select(ReservationDB).where(
        ReservationDB.company_id == body.company_id, ReservationDB.status.in_(ACTIVE),
        ReservationDB.ends_at > utc_now()))).scalars().all()
    for booking in bookings:
        table = incoming.get(booking.table_id)
        if table is None or table.seats < booking.guests:
            raise HTTPException(409, 'Cannot remove a booked table or reduce capacity below booked guests')
    for table_id, old in previous.items():
        if table_id not in incoming:
            old.is_active = False  # Preserve history and foreign keys.
            old.order_qr_hash = None  # A removed/re-added table requires a fresh QR.
    for item in body.tables:
        old = previous.get(item.table_id)
        if old is None:
            if await db.get(DiningTableDB, item.table_id) is not None:
                raise HTTPException(409, 'Table ID is already in use')
            db.add(DiningTableDB(company_id=body.company_id, **item.dict()))
        else:
            for field, value in item.dict().items():
                setattr(old, field, value)
            old.is_active = True
    plan.width, plan.height, plan.rooms = width, height, rooms
    plan.version += 1
    await db.flush()
    return {'version': plan.version}


async def validate_slot(db, body, exclude=None):
    now = utc_now()
    if body.starts_at < now-timedelta(minutes=1) or body.starts_at > now+timedelta(days=365):
        raise HTTPException(422, 'Booking must start between now and one year ahead')
    table = (await db.execute(select(DiningTableDB).where(
        DiningTableDB.table_id == body.table_id, DiningTableDB.company_id == body.company_id,
        DiningTableDB.is_active.is_(True)))).scalar_one_or_none()
    if table is None:
        raise HTTPException(404, 'Table not found')
    if body.guests > table.seats:
        raise HTTPException(422, 'Guest count exceeds table capacity')
    query = select(ReservationDB.reservation_id).where(ReservationDB.company_id == body.company_id,
        ReservationDB.table_id == body.table_id, ReservationDB.status.in_(ACTIVE),
        ReservationDB.starts_at < body.ends_at, ReservationDB.ends_at > body.starts_at)
    if exclude is not None:
        query = query.where(ReservationDB.reservation_id != exclude)
    if (await db.execute(query.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(409, 'Table is already booked for this interval')


def guest_details(body, actor, manage):
    if manage:
        if not body.guest_name or not body.guest_phone:
            raise HTTPException(422, 'Guest name and phone are required')
        return {'guest_name': body.guest_name, 'guest_phone': body.guest_phone, 'user_id': None}
    if body.guest_name is not None or body.guest_phone is not None:
        raise HTTPException(403, 'Clients can only book for themselves using profile details')
    return {'guest_name': f'{actor.name} {actor.surname}'.strip()[:100],
            'guest_phone': actor.phone, 'user_id': actor.user_id}


async def create_booking(db, body, actor):
    await lock_company(db, body.company_id)
    _, manage = await permissions(db, actor.user_id, body.company_id)
    details = guest_details(body, actor, manage)
    values = {**body.dict(exclude={'guest_name', 'guest_phone'}), **details}
    existing = (await db.execute(select(ReservationDB).where(ReservationDB.company_id == body.company_id,
        ReservationDB.creator_id == actor.user_id, ReservationDB.request_id == body.request_id))).scalar_one_or_none()
    if existing:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise HTTPException(409, 'Request ID was already used for different booking details')
        return BookingResponse.from_orm(existing)
    await validate_slot(db, body)
    booking = ReservationDB(**values, creator_id=actor.user_id, updater_id=actor.user_id)
    db.add(booking)
    await db.flush()
    return BookingResponse.from_orm(booking)


async def owned_booking(db, reservation_id, company_id, actor):
    await lock_company(db, company_id)
    _, manage = await permissions(db, actor.user_id, company_id)
    booking = (await db.execute(select(ReservationDB).where(
        ReservationDB.reservation_id == reservation_id, ReservationDB.company_id == company_id))).scalar_one_or_none()
    if booking is None or not (manage or booking.user_id == actor.user_id):
        raise HTTPException(404, 'Reservation not found')
    return booking, manage


async def reschedule(db, reservation_id, body, actor):
    booking, manage = await owned_booking(db, reservation_id, body.company_id, actor)
    if booking.version != body.version or booking.status != 'confirmed':
        raise HTTPException(409, 'Reservation changed or is no longer confirmed')
    if not manage and booking.starts_at <= utc_now():
        raise HTTPException(409, 'An ongoing reservation can only be changed by staff')
    details = guest_details(body, actor, manage)
    await validate_slot(db, body, exclude=reservation_id)
    # Staff editing a registered client's booking must preserve its owner.
    details.pop('user_id')
    for field, value in {**body.dict(exclude={'guest_name', 'guest_phone', 'request_id', 'version'}), **details}.items():
        setattr(booking, field, value)
    booking.version += 1
    booking.updater_id = actor.user_id
    await db.flush()
    return BookingResponse.from_orm(booking)


async def change_status(db, reservation_id, body, actor):
    booking, manage = await owned_booking(db, reservation_id, body.company_id, actor)
    if booking.version != body.version:
        raise HTTPException(409, 'Reservation changed; reload before updating')
    if not manage and (body.status != 'canceled' or booking.starts_at <= utc_now()):
        raise HTTPException(403, 'Clients can only cancel their future reservations')
    transitions = {'confirmed': {'seated', 'canceled'}, 'seated': {'completed'}}
    if body.status not in transitions.get(booking.status, set()):
        raise HTTPException(409, 'Invalid reservation status transition')
    if body.status == 'seated' and not booking.starts_at <= utc_now() < booking.ends_at:
        raise HTTPException(409, 'Guests can be seated only during the reserved interval')
    booking.status = body.status
    booking.version += 1
    booking.updater_id = actor.user_id
    await db.flush()
    return BookingResponse.from_orm(booking)
