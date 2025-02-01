from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from navigations.container.model_dal import ContainerDal


async def __check_container_order_numbers(session: AsyncSession, order_number: int, screen_id: UUID) -> bool:
    async with session.begin():
        container_dal = ContainerDal(session)
        containers = await container_dal.get_all_containers()
        if containers is not None:
            list_order_numbers = [container.container_order_number for container in containers if container.screen_id == screen_id]
            return order_number not in list_order_numbers and order_number >= 0
        return True
