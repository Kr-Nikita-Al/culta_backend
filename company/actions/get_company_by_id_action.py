from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from company.model_dal import CompanyDal
from db import CompanyDB


async def __get_company_by_id(company_id: UUID, session: AsyncSession) -> Union[CompanyDB, None]:
    async with session.begin():
        company_dal = CompanyDal(session)
        company = await company_dal.get_company_by_id(
            company_id=company_id
        )
        return company
