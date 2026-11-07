from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db import UserDB, CompanyDB
from db.session import get_db
from user.actions import __get_user_from_token
from order.api_handlers import OrderRoute
from reservations import service
from reservations.schemas import LayoutRequest, BookingRequest, RescheduleRequest, StatusRequest, BoardResponse, BookingResponse

from company.modules import module_guard
reservation_router = APIRouter(route_class=OrderRoute, dependencies=[Depends(module_guard('reservations'))])


@reservation_router.get('/companies')
async def companies(db: AsyncSession = Depends(get_db), actor: UserDB = Depends(__get_user_from_token)):
    # Public selection exposes no internal company settings or contact data.
    async with db.begin():
        rows = (await db.execute(select(CompanyDB.company_id, CompanyDB.company_name).where(
            CompanyDB.is_active.is_(True), CompanyDB.reservations_enabled.is_(True)).order_by(CompanyDB.company_name, CompanyDB.company_id))).all()
        return [{'company_id': row.company_id, 'company_name': row.company_name} for row in rows]


@reservation_router.get('/board', response_model=BoardResponse)
async def get_board(company_id: UUID, starts_at: datetime, ends_at: datetime,
                    db: AsyncSession = Depends(get_db), actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        return await service.board(db, company_id, starts_at, ends_at, actor)


@reservation_router.put('/layout')
async def layout(body: LayoutRequest, db: AsyncSession = Depends(get_db), actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        return await service.save_layout(db, body, actor)


@reservation_router.post('', response_model=BookingResponse)
async def create(body: BookingRequest, db: AsyncSession = Depends(get_db), actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        return await service.create_booking(db, body, actor)


@reservation_router.put('/{reservation_id}', response_model=BookingResponse)
async def edit(reservation_id: UUID, body: RescheduleRequest, db: AsyncSession = Depends(get_db),
               actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        return await service.reschedule(db, reservation_id, body, actor)


@reservation_router.patch('/{reservation_id}/status', response_model=BookingResponse)
async def status(reservation_id: UUID, body: StatusRequest, db: AsyncSession = Depends(get_db),
                 actor: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        return await service.change_status(db, reservation_id, body, actor)
