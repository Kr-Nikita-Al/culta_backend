from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.screen.model_dal import ScreenDal


async def __delete_screen(screen_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        screen_dal = ScreenDal(session)
        deleted_screen_id = await screen_dal.delete_screen(
            screen_id=screen_id
        )
        return deleted_screen_id

