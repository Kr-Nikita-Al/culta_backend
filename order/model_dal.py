from uuid import UUID
from typing import Union, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload

from db import OrderDB, OrderProductAssociationDB, STATUS_TYPE


class OrderDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_order(self, kwargs, creator_user_id: UUID) -> OrderDB:
        new_order = OrderDB(
            comment=kwargs["comment"],
            cocking_time=kwargs["cocking_time"],
            company_id=kwargs["company_id"],
            user_id=kwargs["user_id"],
            staff_id=creator_user_id,
            creator_id=creator_user_id,
            updater_id=creator_user_id
        )
        self.db_session.add(new_order)
        await self.db_session.flush()
        return new_order

    async def get_order_by_id(self, order_id: UUID) -> Union[OrderDB, None]:
        query = select(OrderDB).where(OrderDB.order_id == order_id) \
                               .options(selectinload(OrderDB.order_items) \
                               .selectinload(OrderProductAssociationDB.product_info))
        res = await self.db_session.execute(query)
        order_row = res.scalars().first()
        return order_row

    async def get_orders_in_company(self, company_id: UUID, statuses: List[STATUS_TYPE]) -> List[OrderDB]:
        if len(statuses) == 0:
            query = select(OrderDB).where(OrderDB.company_id == company_id) \
                                   .options(selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        else:
            query = select(OrderDB).where(OrderDB.company_id == company_id) \
                                   .where(OrderDB.status.in_(statuses)) \
                                   .options(selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        res = await self.db_session.execute(query)
        order_rows = res.unique().scalars().all()
        return order_rows

    async def get_user_orders(self, user_id: UUID, statuses: List[STATUS_TYPE]) -> List[OrderDB]:
        if len(statuses) == 0:
            query = select(OrderDB).where(OrderDB.user_id == user_id) \
                                   .options(selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
        else:
            query = select(OrderDB).where(OrderDB.user_id == user_id) \
                                   .where(OrderDB.status.in_(statuses)) \
                                   .options(selectinload(OrderDB.order_items) \
                                   .selectinload(OrderProductAssociationDB.product_info))
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
