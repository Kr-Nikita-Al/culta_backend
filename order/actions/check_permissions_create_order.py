from user_role.model_user_roles import UserRoleModel


async def __check_permissions_create_order(user_role_model: UserRoleModel) -> bool:
    """
      TODO: добавить возможность создать заказ пользователю
      :param company_id:
      :param db:
      :param cur_user:
      :return:
      """
    # Создать в заведении может владелец, администратор или официант
    return user_role_model.is_owner or user_role_model.is_admin or user_role_model.is_waiter
