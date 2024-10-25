from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.container.model_dal import ContainerDal


async def __update_container_by_id(update_container_params: Dict, container_id: UUID, session: AsyncSession) -> Union[UUID, None]:
    async with session.begin():
        container = ContainerDal(session)
        updated_container_id = await container.update_container(
            container_id=container_id,
            **update_container_params
        )
        return updated_container_id
