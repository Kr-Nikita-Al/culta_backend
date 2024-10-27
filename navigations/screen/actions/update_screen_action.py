from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.screen.model_dal import ScreenDal


async def __update_screen_by_id(update_screen_params: Dict, screen_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        screen = ScreenDal(session)
        updated_screen_id = await screen.update_screen(
            screen_id=screen_id,
            **update_screen_params
        )
        return updated_screen_id
