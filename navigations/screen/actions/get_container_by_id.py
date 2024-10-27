from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ScreenDB
from navigations.screen.model_dal import ScreenDal


async def __get_screen_by_id(screen_id: UUID, session: AsyncSession) -> Union[ScreenDB, None]:
    async with session.begin():
        screen_dal = ScreenDal(session)
        screen = await screen_dal.get_screen_by_id(
            screen_id=screen_id
        )
        return screen
