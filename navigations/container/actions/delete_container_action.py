from typing import Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.container.model_dal import ContainerDal


async def __delete_container(container_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        container_dal = ContainerDal(session)
        deleted_container_id = await container_dal.delete_container(
            container_id=container_id
        )
        return deleted_container_id

