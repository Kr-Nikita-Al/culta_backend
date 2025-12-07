from uuid import UUID
from typing import Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload

from db import OrderDB, OrderProductAssociationDB


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
        if order_row is not None:
            return order_row
        return None

    # async def get_images_by_company_id(self, company_id: UUID) -> List[ImageDB]:
    #     query = select(ImageDB).where(ImageDB.company_id == company_id)
    #     res = await self.db_session.execute(query)
    #     image_row = res.unique().scalars().all()
    #     if image_row is not None:
    #         return image_row
    #     return []
    #
    # async def delete_image(self, image_id: UUID) -> UUID:
    #     query = delete(ImageDB).where(ImageDB.image_id == image_id)
    #     await self.db_session.execute(query)
    #     return image_id
    #
    # async def update_image(self, image_id: UUID, **kwargs) -> Union[UUID, None]:
    #     query = update(ImageDB).where(and_(ImageDB.image_id == image_id,
    #                                        ImageDB.is_used == False)) \
    #         .values(kwargs) \
    #         .returning(ImageDB.image_id)
    #     res = await self.db_session.execute(query)
    #     update_image_id_row = res.unique().fetchone()
    #     if update_image_id_row is not None:
    #         return update_image_id_row[0]
    #     return None
