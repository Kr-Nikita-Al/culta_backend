from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from image.model_dal import ImageDal


async def __delete_image(image_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        image_dal = ImageDal(session)
        deleted_image_id = await image_dal.delete_image(
            image_id=image_id
        )
        return deleted_image_id

