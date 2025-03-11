from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from image.model_dal import ImageDal
from utils.constants import EMPTY_UUID


async def __update_status_used_image(images_upd_dict: Dict, session: AsyncSession):
    async with session.begin():
        image = ImageDal(session)
        for old_image_id in images_upd_dict.keys():
            if old_image_id != EMPTY_UUID:
                _ = await image.update_image(
                    image_id=old_image_id,
                    is_used=False
                )
            if images_upd_dict[old_image_id] != EMPTY_UUID:
                _ = await image.update_image(
                    image_id=images_upd_dict[old_image_id],
                    is_used=True
                )
