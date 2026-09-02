from sqlalchemy.ext.asyncio import AsyncSession

from order.order_product_association.interface_request import CreateOrderProductRequest
from order.order_product_association.interface_response import CreateOrderProductResponse
from order.order_product_association.model_dal import OrderProductAssociationDal


async def __create_order_product_action(order_body: CreateOrderProductRequest,
                                        session: AsyncSession) -> CreateOrderProductResponse:
    async with session.begin():
        order_product_dal = OrderProductAssociationDal(session)
        order_product_db = await order_product_dal.create_order_product(
            order_body.__dict__
        )
        return CreateOrderProductResponse(
            id=order_product_db.id,
            order_id=order_product_db.order_id,
            product_card_id=order_product_db.product_card_id,
            quantity=order_product_db.quantity,
        )
