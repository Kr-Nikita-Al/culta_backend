from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from image.interface_request import CreateImageRequest
from image.interface_response import CreateImageInterface
from image.model_dal import ImageDal


async def __create_image(image_body: CreateImageRequest, user_id: UUID, session: AsyncSession) -> CreateImageInterface:
    async with session.begin():
        image_dal = ImageDal(session)
        image_db = await image_dal.create_image(
            image_body.__dict__, creator_user_id=user_id
        )
        return CreateImageInterface(
            image_id=image_db.image_id,
            company_id=image_db.company_id,
            company_group_id=image_db.company_group_id,
            title=image_db.title,
            file_name=image_db.file_name,
            type_col=image_db.type_col,
            image_type=image_db.image_type,
            file_path=image_db.file_path,
            resolution=image_db.resolution,
            tags=image_db.tags,
            order_number=image_db.order_number,
            size=image_db.size,
            width=image_db.width,
            height=image_db.height,
            is_hidden=image_db.is_hidden,
            is_used=image_db.is_used,
            creator_id=image_db.creator_id,
            time_created=image_db.time_created
        )
