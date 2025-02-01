from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.screen.model_dal import ScreenDal


async def __check_screen_order_numbers(session: AsyncSession, order_number: int, company_id: UUID) -> bool:
    async with session.begin():
        screen_dal = ScreenDal(session)
        screens = await screen_dal.get_all_screens()
        if screens is not None:
            list_order_numbers = [screen.screen_order_number for screen in screens if screen.company_id == company_id]
            return order_number not in list_order_numbers and order_number >= 0
        return True
