from db import STATUS_TYPE
from user_role.model_user_roles import UserRoleModel


async def __check_permissions_update_status(user_role_model: UserRoleModel,
                                            old_status: STATUS_TYPE,
                                            new_status: STATUS_TYPE):
    """
    Кейсы официанта:
    1. Созданный заказ можно отменить (нет в наличии) или закрыть (сразу выдать)
    2. Завершенный заказ можно только закрыть
    Кейсы повара:
    1. Созданный заказ можно отменить (нет в наличии) или перевести в статус приготовления
    2. Взятый на приготовление заказ можно только завершить
    Кейсы администратора/владельца:
    1. Созданный заказ можно отменить (нет в наличии), закрыть (сразу выдали) или перевести
    в статус готовки (передать на кухню)
    2. Взятый на приготовление заказ можно только завершить
    3. Завершенный заказ можно только закрыть
    :param old_status:
    :param new_status:
    :return:
    """
    if user_role_model.is_waiter:
        if old_status == STATUS_TYPE.CREATED and new_status in [STATUS_TYPE.CANCELED,
                                                                STATUS_TYPE.CLOSED]:
            return True
        if old_status == STATUS_TYPE.COMPLETED and new_status == STATUS_TYPE.CLOSED:
            return True
    if user_role_model.is_cook:
        if old_status == STATUS_TYPE.CREATED and new_status in [STATUS_TYPE.PROCESSING,
                                                                STATUS_TYPE.CANCELED]:
            return True
        if old_status == STATUS_TYPE.PROCESSING and new_status == STATUS_TYPE.COMPLETED:
            return True
    if user_role_model.is_owner or user_role_model.is_admin:
        if old_status == STATUS_TYPE.CREATED and new_status in [STATUS_TYPE.PROCESSING,
                                                                STATUS_TYPE.CANCELED,
                                                                STATUS_TYPE.CLOSED]:
            return True
        if old_status == STATUS_TYPE.PROCESSING and new_status == STATUS_TYPE.COMPLETED:
            return True
        if old_status == STATUS_TYPE.COMPLETED and new_status == STATUS_TYPE.CLOSED:
            return True
    return False
