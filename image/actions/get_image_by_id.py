from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ImageDB
from image.model_dal import ImageDal


async def __get_image_by_id(image_id: UUID, session: AsyncSession) -> Union[ImageDB, None]:
    async with session.begin():
        image_dal = ImageDal(session)
        image = await image_dal.get_image_by_id(
            image_id=image_id
        )
        return image
