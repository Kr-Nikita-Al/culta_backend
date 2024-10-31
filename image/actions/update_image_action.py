from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from image.model_dal import ImageDal


async def __update_image_by_id(update_image_params: Dict, image_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        image = ImageDal(session)
        updated_image_id = await image.update_image(
            image_id=image_id,
            **update_image_params
        )
        return updated_image_id
