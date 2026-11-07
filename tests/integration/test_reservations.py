import asyncio
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, update, func
from db import ReservationDB, DiningTableDB, UserRoleDB
from db.check_model import utc_now
from reservations import service
from reservations.schemas import BookingRequest

pytestmark = pytest.mark.integration


def test_resizable_floor_preserves_legacy_size_and_rejects_clipping(pg):
    t = table()
    t.update(x=1400, y=850)
    room = dict(room_id=str(uuid4()),label='Большой зал',x=0,y=0,width=1500,height=950)
    payload = dict(company_id=str(pg.ids['company_a']),version=0,tables=[t],rooms=[room],width=1600,height=1000)
    response = pg.client.put('/reservations/layout',headers=pg.headers(),json=payload)
    assert response.status_code == 200, response.text
    state = board(pg).json()
    assert (state['width'],state['height']) == (1600,1000)
    assert state['tables'][0]['x'] == 1400
    assert layout(pg,[t],version=1).status_code == 200
    assert board(pg).json()['width'] == 1600
    payload.update(version=2,width=1000)
    assert pg.client.put('/reservations/layout',headers=pg.headers(),json=payload).status_code == 422
    assert board(pg).json()['version'] == 2
    payload.update(width=1600, height=1000)
    assert pg.client.put('/reservations/layout',headers=pg.headers('waiter_a'),json=payload).status_code == 403


@pytest.mark.parametrize('width,height',[(299,600),(1000,199),(4001,600),(1000,2401),(1000.5,600)])
def test_invalid_floor_size(pg,width,height):
    response = pg.client.put('/reservations/layout',headers=pg.headers(),json=dict(
        company_id=str(pg.ids['company_a']),version=0,tables=[],width=width,height=height))
    assert response.status_code == 422


def table(**changes):
    return dict(table_id=str(uuid4()), label='Стол 1', shape='square', seats=4,
                x=150, y=150, width=90, height=90, **changes)


def layout(pg, tables, version=0, role='admin_a', company='company_a'):
    return pg.client.put('/reservations/layout', headers=pg.headers(role), json={
        'company_id': str(pg.ids[company]), 'version': version, 'tables': tables})


def setup(pg):
    t = table()
    response = layout(pg, [t])
    assert response.status_code == 200, response.text
    return t


def body(pg, t, **changes):
    start = utc_now()+timedelta(hours=2)
    return {**dict(company_id=str(pg.ids['company_a']), table_id=t['table_id'], request_id=str(uuid4()),
        guests=3, starts_at=start.isoformat(), ends_at=(start+timedelta(hours=2)).isoformat()), **changes}


def create(pg, payload, role='client_a'):
    return pg.client.post('/reservations', headers=pg.headers(role), json=payload)


def board(pg, role='admin_a', company='company_a'):
    return pg.client.get('/reservations/board', headers=pg.headers(role), params={
        'company_id': str(pg.ids[company]), 'starts_at': utc_now().isoformat(),
        'ends_at': (utc_now()+timedelta(days=1)).isoformat()})


def status(pg, booking, value, role='client_a', version=None):
    return pg.client.patch(f'/reservations/{booking["reservation_id"]}/status', headers=pg.headers(role), json={
        'company_id': booking['company_id'], 'version': version or booking['version'], 'status': value})


def test_whole_table_booking_identity_privacy_and_overlap(pg):
    t = setup(pg)
    payload = body(pg, t)
    created = create(pg, payload)
    assert created.status_code == 200, created.text
    b = created.json()
    assert b['user_id'] == str(pg.ids['client_a']) and b['guest_name'] == 'Test client_a'
    assert create(pg, payload).json() == b  # Request retry creates no duplicate.
    assert create(pg, {**payload, 'request_id': str(uuid4())}, 'client_b').status_code == 409
    assert create(pg, {**payload, 'guests': 1}).status_code == 409  # same request, different details
    public = board(pg, 'client_b').json()
    assert public['bookings'] == [] and len(public['occupancy']) == 1
    assert 'guest_name' not in public['occupancy'][0] and 'user_id' not in public['occupancy'][0]
    assert len(board(pg, 'client_a').json()['bookings']) == 1
    assert len(board(pg).json()['bookings']) == 1
    assert board(pg, 'admin_b').json()['bookings'] == []
    assert status(pg, b, 'canceled', 'client_b').status_code == 404
    assert status(pg, b, 'canceled', 'admin_b').status_code == 404


def test_adjacent_intervals_cancel_and_reschedule(pg):
    t = setup(pg)
    p = body(pg, t)
    b = create(pg, p).json()
    adjacent = body(pg, t, starts_at=p['ends_at'], ends_at=(utc_now()+timedelta(hours=6)).isoformat())
    assert create(pg, adjacent).status_code == 200
    conflicting = {**p, 'version': b['version'], 'ends_at': (utc_now()+timedelta(hours=5)).isoformat()}
    assert pg.client.put('/reservations/'+b['reservation_id'], headers=pg.headers('client_a'), json=conflicting).status_code == 409
    new = {**p, 'version': b['version'], 'guests': 2}
    response = pg.client.put('/reservations/'+b['reservation_id'], headers=pg.headers('client_a'), json=new)
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed['guests'] == 2 and changed['version'] == 2
    assert status(pg, b, 'canceled').status_code == 409  # stale version
    assert status(pg, changed, 'canceled').status_code == 200
    assert create(pg, {**p, 'request_id': str(uuid4())}, 'client_b').status_code == 200


@pytest.mark.parametrize('role', ['client_a', 'waiter_a', 'cook_a', 'admin_b'])
def test_only_plan_editors_can_save(pg, role):
    assert layout(pg, [table()], role=role).status_code == 403


def test_rooms_roundtrip_versioning_and_legacy_client(pg):
    t = setup(pg)
    room = dict(room_id=str(uuid4()), label='У окна', x=20, y=20, width=400, height=300)
    payload = dict(company_id=str(pg.ids['company_a']), version=1, tables=[t], rooms=[room])
    assert pg.client.put('/reservations/layout', headers=pg.headers('waiter_a'), json=payload).status_code == 403
    assert pg.client.put('/reservations/layout', headers=pg.headers(), json=payload).json() == {'version': 2}
    assert board(pg).json()['rooms'] == [room]
    assert board(pg, company='company_b').json()['rooms'] == []
    assert pg.client.put('/reservations/layout', headers=pg.headers(), json=payload).status_code == 409
    assert layout(pg, [t], version=2).status_code == 200  # omission preserves rooms
    assert board(pg).json()['rooms'] == [room]
    payload.update(version=3, rooms=[])
    assert pg.client.put('/reservations/layout', headers=pg.headers(), json=payload).status_code == 200
    assert board(pg).json()['rooms'] == []


@pytest.mark.parametrize('changes', [{'x': 900}, {'width': 99}, {'height': 700}, {'label': ' '}, {'x': 2.5}])
def test_invalid_room_geometry_is_rejected(pg, changes):
    room = dict(room_id=str(uuid4()), label='Комната', x=20, y=20, width=400, height=300)
    response = pg.client.put('/reservations/layout', headers=pg.headers(), json={
        'company_id': str(pg.ids['company_a']), 'version': 0, 'tables': [], 'rooms': [{**room, **changes}]})
    assert response.status_code == 422


def test_duplicate_rooms_are_rejected(pg):
    room = dict(room_id=str(uuid4()), label='Комната', x=20, y=20, width=400, height=300)
    response = pg.client.put('/reservations/layout', headers=pg.headers(), json={
        'company_id': str(pg.ids['company_a']), 'version': 0, 'tables': [], 'rooms': [room, room]})
    assert response.status_code == 422


def test_hostess_and_waiter_workflow(pg):
    with pg.engine.begin() as conn:
        conn.execute(update(UserRoleDB).where(UserRoleDB.user_id == pg.ids['cook_a']).values(role='PORTAL_ROLE_HOSTESS'))
    t = table()
    assert layout(pg, [t], role='cook_a').status_code == 200
    for actor in ('cook_a', 'waiter_a'):
        p = body(pg, t, starts_at=(utc_now()-timedelta(seconds=5)).isoformat(),
                 ends_at=(utc_now()+timedelta(hours=1)).isoformat(), guest_name='Гость', guest_phone='+79990000000')
        response = create(pg, p, actor)
        assert response.status_code == 200, response.text
        booking = response.json()
        assert booking['user_id'] is None
        seated = status(pg, booking, 'seated', actor)
        assert seated.status_code == 200, seated.text
        assert status(pg, seated.json(), 'completed', actor).status_code == 200
    with pg.engine.begin() as conn:
        conn.execute(update(UserRoleDB).where(UserRoleDB.user_id == pg.ids['cook_a']).values(is_active=False))
    assert not board(pg, 'cook_a').json()['can_edit_plan']


def test_layout_version_and_protected_booked_table(pg):
    t = setup(pg)
    assert layout(pg, [t], version=0).status_code == 409
    b = create(pg, body(pg, t)).json()
    assert layout(pg, [], version=1).status_code == 409
    assert layout(pg, [{**t, 'seats': 2}], version=1).status_code == 409
    assert layout(pg, [{**t, 'x': 300}], version=1).status_code == 200
    assert status(pg, b, 'canceled').status_code == 200
    assert layout(pg, [], version=2).status_code == 200
    assert board(pg).json()['tables'] == []
    assert create(pg, body(pg, t)).status_code == 404
    with pg.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(ReservationDB)) == 1
        assert conn.scalar(select(func.count()).select_from(DiningTableDB)) == 1


@pytest.mark.parametrize('bad', ['capacity', 'past', 'naive', 'duration', 'forged_identity', 'fraction', 'foreign_table'])
def test_invalid_booking_rolls_back(pg, bad):
    t = setup(pg)
    p = body(pg, t)
    changes = {
        'capacity': {'guests': 5}, 'past': {'starts_at': (utc_now()-timedelta(hours=1)).isoformat()},
        'naive': {'starts_at': '2026-10-01T12:00:00'}, 'duration': {'ends_at': p['starts_at']},
        'forged_identity': {'guest_name': 'Someone else', 'guest_phone': '000'},
        'fraction': {'guests': 1.5}, 'foreign_table': {'table_id': str(uuid4())},
    }
    result = create(pg, {**p, **changes[bad]})
    assert result.status_code == (403 if bad == 'forged_identity' else 404 if bad == 'foreign_table' else 422), result.text
    assert board(pg).json()['bookings'] == []


def test_concurrent_booking_requests_only_one_wins(pg):
    t = setup(pg)
    p = body(pg, t)
    actor = SimpleNamespace(user_id=pg.ids['client_a'], name='Test', surname='Client', phone='000')

    async def run():
        async def one():
            async with pg.sessions() as db:
                try:
                    async with db.begin():
                        await service.create_booking(db, BookingRequest(**{**p, 'request_id': uuid4()}), actor)
                    return 200
                except HTTPException as error:
                    return error.status_code
        return await asyncio.gather(one(), one())

    assert sorted(asyncio.run(run())) == [200, 409]
    assert len(board(pg).json()['bookings']) == 1


def test_tenant_table_ids_cannot_be_reused_or_booked(pg):
    t = table()
    assert layout(pg, [t], role='admin_b', company='company_b').status_code == 200
    assert layout(pg, [t]).status_code == 409
    assert create(pg, body(pg, t)).status_code == 404
    assert board(pg).json()['version'] == 0  # failed layout creation rolled back
