from typing import Union, List

from sqlalchemy.ext.asyncio import AsyncSession

from company.model_dal import CompanyDal
from db import CompanyDB


async def __get_all_companies(session: AsyncSession) -> Union[List[CompanyDB], None]:
    async with session.begin():
        company_dal = CompanyDal(session)
        companies = await company_dal.get_all_companies()
        return companies
