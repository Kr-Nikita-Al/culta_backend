from typing import Dict, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from db import CompanyDB

from company.edit_lease import assert_company_edit
from company.model_dal import CompanyDal
from utils.company_references import validate_company_references


async def __update_company_by_id(update_company_params: Dict, company_id: UUID, session: AsyncSession, lease_token=None) -> Union[UUID, None]:
    async with session.begin():
        current = (await session.execute(select(CompanyDB).where(CompanyDB.company_id == company_id)
            .with_for_update(of=CompanyDB).execution_options(populate_existing=True))).unique().scalar_one_or_none()
        if current is None:
            return None
        await assert_company_edit(session, current, update_company_params.get('updater_id'), lease_token)
        if any(key in update_company_params for key in ('bonus_payment_perc', 'bonus_accrual_perc')):
            payment = update_company_params.get('bonus_payment_perc', current.bonus_payment_perc) or 0
            accrual = update_company_params.get('bonus_accrual_perc', current.bonus_accrual_perc) or 0
            if accrual > payment:
                raise HTTPException(422, 'Accrual percentage must not exceed redemption percentage')
            update_company_params = dict(update_company_params, infrastructure_version=current.infrastructure_version + 1)
        # Serialize partial settings updates and keep the legacy summary consistent.
        fields = ('allow_client_orders_inside', 'allow_client_orders_outside')
        if any(key in update_company_params for key in (*fields, 'is_can_client_create_order')):
            result = await session.execute(select(CompanyDB).where(
                CompanyDB.company_id == company_id).with_for_update(of=CompanyDB))
            current = result.unique().scalar_one_or_none()
            if current is None:
                return None
            update_company_params = dict(update_company_params)
            legacy = update_company_params.pop('is_can_client_create_order', None)
            # Old callers can still toggle both. Explicit context fields take precedence.
            for field in fields:
                update_company_params[field] = update_company_params.get(
                    field, legacy if legacy is not None else getattr(current, field))
            update_company_params['is_can_client_create_order'] = any(
                update_company_params[field] for field in fields)
        await validate_company_references(session, company_id, update_company_params,
            image_fields=('image_picture_id', 'image_icon_id'), screen_fields=('basic_screen_id',))
        company = CompanyDal(session)
        updated_company_id = await company.update_company(
            company_id=company_id,
            **update_company_params
        )
        return updated_company_id
