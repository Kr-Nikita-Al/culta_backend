from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db import ContainerDB
from navigations.container.model_dal import ContainerDal


async def __get_container_by_id(container_id: UUID, session: AsyncSession) -> Union[ContainerDB, None]:
    async with session.begin():
        container_dal = ContainerDal(session)
        container = await container_dal.get_container_by_id(
            container_id=container_id
        )
        return container
