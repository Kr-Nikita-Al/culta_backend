from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from company.models.model_dal import CompanyDal


async def __update_company_by_id(update_company_params: Dict, company_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        user = CompanyDal(session)
        updated_company_id = await user.update_company(
            company_id=company_id,
            **update_company_params
        )
        return updated_company_id
