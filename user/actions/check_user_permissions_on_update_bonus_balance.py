from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from company.actions import __get_company_by_id
from db import UserDB
from user_role.actions import __get_user_role_model


async def __check_user_permissions_on_update_bonus_balance(target_user: UserDB, current_user: UserDB,
                                                           is_write_off: bool, company_id: UUID,
                                                           db: AsyncSession) -> bool:
    """
    Списать/начислить бонусы на бонусный баланс пользователя может:
    1) владелец/администратор/официант заведения, где процент списания/начисления больше 0
    2) нельзя самому себе начислить/списать бонусы
    :param target_user: обновляемый пользователь
    :param current_user: пользователь, который хочет начислить/списать бонусы
    :param db: сессия
    :return: возможность обновить данные пользователя
    """
    if target_user.user_id == current_user.user_id:
        return False
    company = await __get_company_by_id(company_id, db)
    if (is_write_off and company.bonus_payment_perc > 0) or ((not is_write_off) and company.bonus_accrual_perc > 0):
        # Проверка прав
        user_role_model = await __get_user_role_model(user_id=current_user.user_id, session=db,
                                                      company_id=company_id)
        if user_role_model.is_owner or user_role_model.is_admin or user_role_model.is_waiter:
            return True
    return False
