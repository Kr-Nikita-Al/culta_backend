from datetime import time
from typing import Union, List
from uuid import UUID

from sqlalchemy import select, update, and_, text, or_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, contains_eager

from db import CompanyDB, ProductCardDB, ImageDB
from product_card.interface_response import GetProductCardResponse
from utils.constants import EMPTY_UUID


class CompanyDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_company(self, company_name: str, address: str, phone: str, email: str,
                             order_number: int, group_id: int, image_picture_id: str,
                             image_icon_id: str, age_limit: bool, work_state: bool, start_time: time,
                             over_time: time
                             ) -> CompanyDB:
        new_company = CompanyDB(
            company_name=company_name,
            address=address,
            phone=phone,
            email=email,
            order_number=order_number,
            group_id=group_id,
            image_picture_id=image_picture_id,
            image_icon_id=image_icon_id,
            age_limit=age_limit,
            work_state=work_state,
            start_time=start_time,
            over_time=over_time
        )
        self.db_session.add(new_company)
        await self.db_session.flush()
        return new_company

    async def delete_company(self, company_id: UUID) -> Union[UUID, None]:
        query = update(CompanyDB).where(and_(CompanyDB.company_id == company_id,
                                             CompanyDB.is_active == True)) \
            .values(is_active=False) \
            .returning(CompanyDB.company_id)
        res = await self.db_session.execute(query)
        deleted_company_id_row = res.unique().fetchone()
        if deleted_company_id_row is not None:
            return deleted_company_id_row[0]
        return None

    async def get_company_by_id(self, company_id: UUID) -> Union[CompanyDB, None]:
        query = select(CompanyDB).where(CompanyDB.company_id == company_id)
        res = await self.db_session.execute(query)
        company_row = res.unique().fetchone()
        if company_row is not None:
            return company_row[0]
        return None

    async def get_all_companies(self) -> Union[List[CompanyDB], None]:
        query = select(CompanyDB)
        res = await self.db_session.execute(query)
        companies_row = res.unique().scalars().all()
        if companies_row is not None:
            return companies_row
        return None

    async def get_company_products_by_id(self, company_id: UUID) -> Union[List[GetProductCardResponse], None]:
        query = select(ProductCardDB).where(and_(ProductCardDB.company_id == company_id,
                                                 ProductCardDB.is_active == True))
        res = await self.db_session.execute(query)
        products_row = res.unique().scalars().all()
        if products_row is not None:
            return products_row
        return None

    async def update_company(self, company_id: UUID, **kwargs) -> Union[UUID, None]:
        query = update(CompanyDB).where(and_(CompanyDB.company_id == company_id,
                                             CompanyDB.is_active == True)) \
            .values(kwargs) \
            .returning(CompanyDB.company_id)
        res = await self.db_session.execute(query)
        update_company_id_row = res.unique().fetchone()
        if update_company_id_row is not None:
            return update_company_id_row[0]
        return None
