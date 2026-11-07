"""Server-side section gate, including ID-only and multipart routes."""
import json
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from db import CompanyDB, OrderDB, CheckDB, ImageDB
from db.session import get_db
from user.actions.get_current_user_from_token_action import __get_user_from_token


async def ensure_enabled(session, company_id, module):
    enabled = await session.scalar(select(getattr(CompanyDB, module + '_enabled')).where(CompanyDB.company_id == company_id))
    if enabled is False:
        raise HTTPException(403, 'Section disabled by the company')


def module_guard(module):
    async def guard(request: Request, db=Depends(get_db), actor=Depends(__get_user_from_token)):
        data = dict(request.query_params)
        try:
            if request.headers.get('content-type', '').startswith('application/json'):
                body = await request.json()
                if isinstance(body, dict):
                    data.update(body)
            elif 'multipart/form-data' in request.headers.get('content-type', ''):
                form = await request.form()
                data.update(json.loads(form.get('metadata', '{}')))
        except (ValueError, TypeError):
            return  # Endpoint validation reports malformed input.
        companies = set()
        async with db.begin():
            if data.get('company_id'):
                try:
                    companies.add(UUID(str(data['company_id'])))
                except ValueError:
                    return
            for key, model in [('order_id', OrderDB), ('check_id', CheckDB), ('image_id', ImageDB)]:
                if data.get(key):
                    try:
                        value = UUID(str(data[key]))
                    except ValueError:
                        return
                    company = await db.scalar(select(model.company_id).where(getattr(model, key) == value))
                    if company:
                        companies.add(company)
            for company in companies:
                await ensure_enabled(db, company, module)
    return guard
