"""Leases are scoped to one editor, not merely to a user or browser account."""
from datetime import timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from sqlalchemy.orm import noload
from sqlalchemy.ext.asyncio import AsyncSession
from db import CompanyDB, UserDB
from db.session import get_db
from user.actions import __get_user_from_token
from user_role.actions import __get_user_role_model

router=APIRouter()
TTL=90

def locked():
    return HTTPException(423,detail={'code':'company_edit_locked',
        'message':'Компания редактируется в другом окне или блокировка истекла. Откройте редактирование заново.'})

async def company_for_edit(db,company_id):
    company=await db.scalar(select(CompanyDB).options(noload('*')).where(
        CompanyDB.company_id==company_id).with_for_update().execution_options(populate_existing=True))
    if company is None or not company.is_active:
        raise HTTPException(404,'Company not found')
    return company

async def assert_company_edit(db,company,user_id,token):
    now=await db.scalar(select(func.clock_timestamp()))
    active=company.edit_lease_expires_at is not None and company.edit_lease_expires_at>now
    # Atomic one-off legacy writes may run only while there is no active editor.
    # A stale token must never fall back to an unprotected write.
    if token is not None or active:
        if not active or token!=company.edit_lease_token or user_id!=company.edit_lease_user_id:
            raise locked()

async def allowed(db,user,company_id):
    role=await __get_user_role_model(user.user_id,db,company_id)
    if not user.is_active or not (role.is_owner or role.is_admin):
        raise HTTPException(403,'Forbidden')

@router.post('/edit-lease')
async def acquire(company_id:UUID,db:AsyncSession=Depends(get_db),user:UserDB=Depends(__get_user_from_token)):
    await allowed(db,user,company_id)
    async with db.begin():
        company=await company_for_edit(db,company_id)
        now=await db.scalar(select(func.clock_timestamp()))
        if company.edit_lease_expires_at and company.edit_lease_expires_at>now:
            raise locked()
        company.edit_lease_token=uuid4()
        company.edit_lease_user_id=user.user_id
        company.edit_lease_expires_at=now+timedelta(seconds=TTL)
        return {'token':company.edit_lease_token,'expires_at':company.edit_lease_expires_at,'ttl_seconds':TTL}

@router.put('/edit-lease')
async def heartbeat(company_id:UUID,x_company_edit_token:UUID=Header(...),
                    db:AsyncSession=Depends(get_db),user:UserDB=Depends(__get_user_from_token)):
    await allowed(db,user,company_id)
    async with db.begin():
        company=await company_for_edit(db,company_id)
        await assert_company_edit(db,company,user.user_id,x_company_edit_token)
        company.edit_lease_expires_at=await db.scalar(select(func.clock_timestamp()))+timedelta(seconds=TTL)
        return {'expires_at':company.edit_lease_expires_at,'ttl_seconds':TTL}

@router.delete('/edit-lease')
async def release(company_id:UUID,x_company_edit_token:UUID=Header(...),
                  db:AsyncSession=Depends(get_db),user:UserDB=Depends(__get_user_from_token)):
    await allowed(db,user,company_id)
    async with db.begin():
        company=await company_for_edit(db,company_id)
        if company.edit_lease_token==x_company_edit_token and company.edit_lease_user_id==user.user_id:
            company.edit_lease_token=None
            company.edit_lease_user_id=None
            company.edit_lease_expires_at=None
        return {'released':True}
