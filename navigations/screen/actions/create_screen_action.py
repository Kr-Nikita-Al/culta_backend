from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.screen.interface_request import CreateScreenRequest
from navigations.screen.interface_response import CreateScreenResponse
from navigations.screen.model_dal import ScreenDal


async def __create_screen(screen_body: CreateScreenRequest, user_id: UUID, session: AsyncSession) -> CreateScreenResponse:
    async with session.begin():
        screen_dal = ScreenDal(session)
        screen_db = await screen_dal.create_screen(
            screen_body.__dict__, creator_user_id=user_id
        )
        return CreateScreenResponse(
            screen_id=screen_db.screen_id,
            company_id=screen_db.company_id,
            company_group_id=screen_db.company_group_id,
            screen_title=screen_db.screen_title,
            screen_sub_title=screen_db.screen_sub_title,
            screen_order_number=screen_db.screen_order_number,
            creator_id=screen_db.creator_id,
            updater_id=screen_db.updater_id,
            time_created=screen_db.time_created,
            time_updated=screen_db.time_updated,
        )
