from ctypes import Union
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from image.model_dal import ImageDal


async def __get_images_by_company_id(company_id: UUID, session: AsyncSession) -> List:
    async with session.begin():
        image_dal = ImageDal(session)
        images = await image_dal.get_images_by_company_id(
            company_id=company_id
        )
        return images
