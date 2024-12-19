from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from company.model_dal import CompanyDal
from company.interface_request import CreateCompanyRequest
from company.interface_response import CreateCompanyResponse


async def __create_company(company_body: CreateCompanyRequest, user_id: UUID, session: AsyncSession) -> CreateCompanyResponse:
    async with session.begin():
        company_dal = CompanyDal(session)
        company_db = await company_dal.create_company(
            company_name=company_body.company_name,
            address=company_body.address,
            phone=company_body.phone,
            email=company_body.email,
            order_number=company_body.order_number,
            group_id=company_body.group_id,
            image_picture_id=company_body.image_picture_id,
            image_icon_id=company_body.image_icon_id,
            age_limit=company_body.age_limit,
            work_state=company_body.work_state,
            start_time=company_body.start_time,
            over_time=company_body.over_time,
            creator_user_id=user_id
        )
        return CreateCompanyResponse(
            company_id=company_db.company_id,
            company_name=company_db.company_name,
            address=company_db.address,
            phone=company_db.phone,
            email=company_db.email,
            is_active=company_db.is_active,
            order_number=company_db.order_number,
            basic_screen_id=company_db.basic_screen_id,
            group_id=company_db.group_id,
            image_picture_id=company_db.image_picture_id,
            image_icon_id=company_db.image_icon_id,
            age_limit=company_db.age_limit,
            work_state=company_db.work_state,
            creator_id=company_db.creator_id,
            updater_id=company_db.updater_id,
            time_created=company_db.time_created,
            time_updated=company_db.time_updated,
            start_time=company_db.start_time,
            over_time=company_db.over_time
        )
