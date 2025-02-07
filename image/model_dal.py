from typing import Union
from uuid import UUID

from fastapi import HTTPException

from sqlalchemy import select, and_, update, delete

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import ImageDB, CompanyDB


class ImageDal:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_image(self, kwargs) -> ImageDB:
        company_id = kwargs["company_id"]
        query = select(CompanyDB).where(and_(CompanyDB.company_id == company_id,
                                             CompanyDB.is_active == True))
        res = await self.db_session.execute(query)
        company_row = res.unique().fetchone()
        if company_row is not None:
            company_id_for_adding = company_row[0].company_id
        else:
            raise HTTPException(status_code=404,
                                detail='Company with id {0} was not exit or deleted before'.format(company_id))
        new_image = ImageDB(
            company_id=company_id_for_adding,
            company_group_id=kwargs["company_group_id"],
            file_name=kwargs["file_name"],
            type_col=kwargs["type_col"],
            image_type=kwargs["image_type"],
            file_path=kwargs["file_path"],
            resolution=kwargs["resolution"],
            tags=kwargs["tags"],
            order_number=kwargs["order_number"],
            size=kwargs["size"],
            width=kwargs["width"],
            height=kwargs["height"],
            is_hidden=kwargs["is_hidden"],
            is_archived=kwargs["is_archived"],
        )
        self.db_session.add(new_image)
        await self.db_session.flush()
        return new_image

    async def get_image_by_id(self, image_id: UUID) -> Union[ImageDB, None]:
        query = select(ImageDB).where(ImageDB.image_id == image_id)
        res = await self.db_session.execute(query)
        image_row = res.scalars().first()
        if image_row is not None:
            return image_row
        return None

    async def delete_image(self, image_id: UUID) -> UUID:
        query = update(ImageDB).where(and_(ImageDB.image_id == image_id,
                                           ImageDB.is_archived == False)) \
                               .values(is_archived=True) \
                               .returning(ImageDB.image_id)
        res = await self.db_session.execute(query)
        deleted_image_id_row = res.unique().fetchone()
        if deleted_image_id_row is not None:
            return deleted_image_id_row[0]
        return None

    async def update_image(self, image_id: UUID, **kwargs) -> Union[UUID, None]:
        query = update(ImageDB).where(and_(ImageDB.image_id == image_id,
                                           ImageDB.is_archived == False))\
                                .values(kwargs)\
                                .returning(ImageDB.image_id)
        res = await self.db_session.execute(query)
        update_image_id_row = res.unique().fetchone()
        if update_image_id_row is not None:
            return update_image_id_row[0]
        return None

