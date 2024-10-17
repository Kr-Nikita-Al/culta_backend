from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from company.models.model_dal import CompanyDal


async def __delete_company(company_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        company_dal = CompanyDal(session)
        deleted_company_id = await company_dal.delete_company(
            company_id=company_id
        )
        return deleted_company_id
