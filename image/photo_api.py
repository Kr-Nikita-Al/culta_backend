"""Company cover and per-role employee avatars, referencing existing images only."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db import CompanyDB, ImageDB, UserRoleDB, UserDB
from db.session import get_db
from user.actions import __get_user_from_token
from s3_directory.storage import S3Client
from utils.constants import EMPTY_UUID, PortalRole

photo_router = APIRouter()
STAFF = {PortalRole.PORTAL_ROLE_OWNER.value, PortalRole.PORTAL_ROLE_ADMIN.value,
         PortalRole.PORTAL_ROLE_MODERATOR.value, PortalRole.PORTAL_ROLE_WAITER.value,
         PortalRole.PORTAL_ROLE_COOK.value, PortalRole.PORTAL_ROLE_HOSTESS.value}


class PhotoSelection(BaseModel):
    image_id: UUID
    class Config:
        extra = 'forbid'


class RolePhotoSelection(BaseModel):
    image_id: UUID | None = None
    apply_to_all: bool | None = None
    class Config:
        extra = 'forbid'


async def own_roles(db, company_id, user_id):
    return (await db.execute(select(UserRoleDB).where(UserRoleDB.company_id == company_id,
        UserRoleDB.user_id == user_id, UserRoleDB.is_active == True,
        UserRoleDB.role.in_(STAFF)).with_for_update(read=True))).scalars().all()


async def active_company(db, company_id):
    row = (await db.execute(select(CompanyDB.company_id).where(CompanyDB.company_id == company_id,
        CompanyDB.is_active == True))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, 'Company not found')


async def photo_data(db, company_id, image_id):
    if image_id in (None, EMPTY_UUID):
        return {'image_id': None, 'url': None}
    image = (await db.execute(select(ImageDB).where(ImageDB.company_id == company_id,
        ImageDB.image_id == image_id, ImageDB.is_hidden == False))).scalar_one_or_none()
    if image is None:
        return {'image_id': None, 'url': None}
    url = await S3Client().generate_get_presigned_url(file_path=image.file_path,
        file_name=image.file_name, company_id=company_id)
    return {'image_id': image.image_id, 'url': url}


async def selected_image(db, company_id, image_id):
    if image_id == EMPTY_UUID:
        return
    found = (await db.execute(select(ImageDB.image_id).where(ImageDB.company_id == company_id,
        ImageDB.image_id == image_id, ImageDB.is_hidden == False).with_for_update(read=True))).scalar_one_or_none()
    if found is None:
        raise HTTPException(422, 'Choose an existing visible image from this company')


@photo_router.get('/options')
async def options(company_id: UUID, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        await active_company(db, company_id)
        if not await own_roles(db, company_id, user.user_id):
            raise HTTPException(403, 'Forbidden')
        images = (await db.execute(select(ImageDB).where(ImageDB.company_id == company_id,
            ImageDB.is_hidden == False).order_by(ImageDB.time_created.desc()))).scalars().all()
        return [{**await photo_data(db, company_id, image.image_id), 'title': image.title or image.file_name,
                 'file_path': image.file_path, 'size': image.size} for image in images]


@photo_router.get('/company')
async def company_photo(company_id: UUID, db: AsyncSession = Depends(get_db)):
    # Only the assigned cover is public, never arbitrary storage images.
    async with db.begin():
        await active_company(db, company_id)
        image_id = (await db.execute(select(CompanyDB.image_picture_id).where(CompanyDB.company_id == company_id))).scalar_one()
        return await photo_data(db, company_id, image_id)


@photo_router.put('/company')
async def set_company_photo(company_id: UUID, body: PhotoSelection, x_company_edit_token: UUID = Header(None), db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        await active_company(db, company_id)
        roles = await own_roles(db, company_id, user.user_id)
        if not any(r.role in ('PORTAL_ROLE_OWNER', 'PORTAL_ROLE_ADMIN') for r in roles):
            raise HTTPException(403, 'Forbidden')
        from company.edit_lease import company_for_edit, assert_company_edit
        company = await company_for_edit(db, company_id)
        await assert_company_edit(db, company, user.user_id, x_company_edit_token)
        await selected_image(db, company_id, body.image_id)
        from sqlalchemy import update
        await db.execute(update(CompanyDB).where(CompanyDB.company_id == company_id).values(
            image_picture_id=body.image_id, updater_id=user.user_id))
        return {'image_id': body.image_id}


@photo_router.get('/my-roles')
async def role_photos(company_id: UUID, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        await active_company(db, company_id)
        roles = await own_roles(db, company_id, user.user_id)
        if not roles:
            raise HTTPException(403, 'Forbidden')
        source = next((r for r in roles if r.avatar_default), None)
        return [{'role': r.role, 'default_role': source.role if source else None,
                 'inherited': bool(source and r.avatar_id in (None, EMPTY_UUID) and r.role != source.role),
                 **await photo_data(db, company_id, r.avatar_id if r.avatar_id not in (None, EMPTY_UUID)
                                    else source.avatar_id if source else None)} for r in roles]


@photo_router.put('/my-role')
async def set_role_photo(company_id: UUID, role: PortalRole, body: RolePhotoSelection,
                         db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    async with db.begin():
        await active_company(db, company_id)
        # Serialize changes across this user's roles, including competing default selections.
        await db.execute(select(UserDB.user_id).where(UserDB.user_id == user.user_id).with_for_update())
        rows = (await db.execute(select(UserRoleDB).where(UserRoleDB.company_id == company_id,
            UserRoleDB.user_id == user.user_id, UserRoleDB.is_active == True,
            UserRoleDB.role.in_(STAFF)).with_for_update())).scalars().all()
        targets = [r for r in rows if r.role == role.value]
        if not targets or role.value not in STAFF:
            raise HTTPException(403, 'Forbidden')
        source = next((r for r in rows if r.avatar_default), None)
        if body.apply_to_all is not None and source and source.role != role.value:
            raise HTTPException(409, 'Only the source role can change the default avatar setting')
        if body.image_id is not None:
            await selected_image(db, company_id, body.image_id)
            for row in targets:
                row.avatar_id = body.image_id
                if body.image_id == EMPTY_UUID:
                    row.avatar_default = False
        if body.apply_to_all is not None:
            if body.apply_to_all and targets[0].avatar_id in (None, EMPTY_UUID):
                raise HTTPException(422, 'Choose a photo for this role first')
            for row in targets:
                row.avatar_default = body.apply_to_all
        return {'image_id': body.image_id}
