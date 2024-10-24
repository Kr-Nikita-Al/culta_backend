from typing import Union
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import select, and_, update

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import ProductCardDB, ItemDB


class ItemDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_item(self, kwargs) -> ProductCardDB:

        product_card_id = kwargs["product_card_id"]
        query = select(ProductCardDB).where(and_(ProductCardDB.product_card_id == product_card_id,
                                                 ProductCardDB.is_active == True))
        res = await self.db_session.execute(query)
        product_card_row = res.fetchone()
        if product_card_row is not None:
            product_card_id_for_adding = product_card_row[0].product_card_id
        else:
            raise HTTPException(status_code=404,
                                detail='Product card with id {0} was not exit'.format(product_card_id))

        new_item = ItemDB(
            product_card_id=product_card_id_for_adding,
            item_row_order=kwargs["item_row_order"],
            item_column_order=kwargs["item_column_order"],
            item_type=kwargs["item_type"],
        )
        self.db_session.add(new_item)
        await self.db_session.flush()
        return new_item

    async def get_item_by_id(self, item_id: UUID) -> Union[ItemDB, None]:
        res = await self.db_session.execute(select(ItemDB).where(ItemDB.item_id == item_id).options(joinedload(ItemDB.product_card_info)))
        item_row = res.scalars().first()
        if item_row is not None:
            return item_row
        return None

