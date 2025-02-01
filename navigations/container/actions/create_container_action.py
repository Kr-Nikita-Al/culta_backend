from sqlalchemy.ext.asyncio import AsyncSession

from navigations.container.interface_request import CreateContainerRequest
from navigations.container.interface_response import CreateContainerResponse
from navigations.container.model_dal import ContainerDal


async def __create_container(container_body: CreateContainerRequest, session: AsyncSession) -> CreateContainerResponse:
    async with session.begin():
        container_dal = ContainerDal(session)
        container_db = await container_dal.create_container(
            container_body.__dict__
        )
        return CreateContainerResponse(
            container_id=container_db.container_id,
            screen_id=container_db.screen_id,
            container_title=container_db.container_title,
            container_sub_title=container_db.container_sub_title,
            container_type=container_db.container_type,
            container_order_number=container_db.container_order_number,
        )
