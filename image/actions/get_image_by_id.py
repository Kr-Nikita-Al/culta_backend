from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ItemDB
from image.model_dal import ImageDal


async def __get_image_by_id(image_id: UUID, is_used: bool, session: AsyncSession) -> Union[ItemDB, None]:
    async with session.begin():
        image_dal = ImageDal(session)
        image = await image_dal.get_image_by_id(
            image_id=image_id, is_used=is_used
        )
        return image
