from uuid import UUID
from typing import Union, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload

from db import OrderDB, OrderProductAssociationDB, STATUS_TYPE, CheckDB, OrderStatusHistoryDB, CompanyDB
from fastapi import HTTPException
from utils.constants import EMPTY_UUID


class OrderDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_order(self, kwargs, creator_user_id: UUID) -> OrderDB:
        if kwargs.get('check_id') and not kwargs.get('client_request_id'):
            # Staff additions retain the visit context of the already locked check.
            visit = (await self.db_session.execute(select(CheckDB.order_context, CheckDB.table_id)
                .where(CheckDB.check_id == kwargs['check_id']))).one()
            kwargs = {**kwargs, 'order_context': visit.order_context, 'table_id': visit.table_id}
        new_order = OrderDB(
            comment=kwargs["comment"],
            cocking_time=kwargs["cocking_time"],
            company_id=kwargs["company_id"],
            user_id=kwargs["user_id"],
            staff_id=EMPTY_UUID if kwargs.get('client_request_id') else creator_user_id,
            order_context=kwargs.get('order_context'),
            table_id=kwargs.get('table_id'),
            client_request_id=kwargs.get('client_request_id'),
            client_request_hash=kwargs.get('client_request_hash'),
            creator_id=creator_user_id,
            updater_id=creator_user_id
        )
        self.db_session.add(new_order)
        await self.db_session.flush()
        await self.append_status_history(new_order.order_id, None, new_order.status, creator_user_id)
        return new_order

    async def append_status_history(self, order_id, old_status, new_status, actor_id, reason=None):
        self.db_session.add(OrderStatusHistoryDB(order_id=order_id,
            old_status=old_status.value if old_status is not None else None,
            new_status=new_status.value, actor_id=actor_id, reason=reason))
        await self.db_session.flush()

    async def get_order_by_id(self, order_id: UUID) -> Union[OrderDB, None]:
        query = select(OrderDB).where(OrderDB.order_id == order_id) \
                               .options(selectinload(OrderDB.check_info), selectinload(OrderDB.order_items) \
                               .selectinload(OrderProductAssociationDB.product_info))
        res = await self.db_session.execute(query)
        order_row = res.scalars().first()
        return order_row

    async def get_orders_in_company(self, company_id: UUID, statuses: List[STATUS_TYPE]) -> List[OrderDB]:
        if len(statuses) == 0:
            query = select(OrderDB).where(OrderDB.company_id == company_id) \
                                   .options(selectinload(OrderDB.check_info), selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        else:
            query = select(OrderDB).where(OrderDB.company_id == company_id) \
                                   .where(OrderDB.status.in_(statuses)) \
                                   .options(selectinload(OrderDB.check_info), selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        res = await self.db_session.execute(query)
        order_rows = res.unique().scalars().all()
        return order_rows

    async def get_user_orders(self, user_id: UUID, statuses: List[STATUS_TYPE]) -> List[OrderDB]:
        if len(statuses) == 0:
            query = select(OrderDB).where(OrderDB.user_id == user_id) \
                                   .options(selectinload(OrderDB.check_info), selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        else:
            query = select(OrderDB).where(OrderDB.user_id == user_id) \
                                   .where(OrderDB.status.in_(statuses)) \
                                   .options(selectinload(OrderDB.check_info), selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        query = query.where(OrderDB.company_id.in_(select(CompanyDB.company_id).where(CompanyDB.orders_enabled.is_(True))))
        res = await self.db_session.execute(query)
        order_rows = res.unique().scalars().all()
        return order_rows

    async def update_order(self, order_id: UUID, **kwargs) -> Union[UUID, None]:
        query = update(OrderDB).where(and_(OrderDB.order_id == order_id,
                                           OrderDB.status != STATUS_TYPE.CLOSED,
                                           OrderDB.status != STATUS_TYPE.CANCELED)) \
            .values(kwargs) \
            .returning(OrderDB.order_id)
        res = await self.db_session.execute(query)
        update_order_id_row = res.unique().fetchone()
        if update_order_id_row is not None:
            return update_order_id_row[0]
        return None

    async def get_order_status_for_update(self, order_id: UUID) -> Union[STATUS_TYPE, None]:
        check_id = (await self.db_session.execute(select(OrderDB.check_id).where(OrderDB.order_id == order_id))).scalar_one_or_none()
        if check_id is not None:
            state = (await self.db_session.execute(select(CheckDB.status).where(CheckDB.check_id == check_id).with_for_update())).scalar_one_or_none()
            if state != 'open':
                raise HTTPException(409, 'Check is closed or canceled')
        query = select(OrderDB.status).where(OrderDB.order_id == order_id).with_for_update()
        res = await self.db_session.execute(query)
        return res.scalar_one_or_none()
