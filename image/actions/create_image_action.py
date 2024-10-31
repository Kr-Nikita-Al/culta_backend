from sqlalchemy.ext.asyncio import AsyncSession

from image.interface_request import CreateImageRequest
from image.interface_response import CreateImageResponse
from image.model_dal import ImageDal


async def __create_image(image_body: CreateImageRequest, session: AsyncSession) -> CreateImageResponse:
    async with session.begin():
        image_dal = ImageDal(session)
        image_db = await image_dal.create_image(
            image_body.__dict__
        )
        return CreateImageResponse(
            image_id=image_db.image_id,
            company_id=image_db.company_id,
            company_group_id=image_db.company_group_id,
            title=image_db.title,
            type_col=image_db.type_col,
            image_type=image_db.image_type,
            url=image_db.url,
            resolution=image_db.resolution,
            tags=image_db.tags,
            order_number=image_db.order_number,
            size=image_db.size,
            width=image_db.width,
            height=image_db.height,
            is_hidden=image_db.is_hidden,
            is_archived=image_db.is_archived,
            creator_id=image_db.creator_id,
            time_created=image_db.time_created
        )
