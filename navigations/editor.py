"""Company-scoped menu editor. Existing mobile navigation entities are reused."""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool, constr, conint, Field
from sqlalchemy import select
from sqlalchemy.orm import noload
from sqlalchemy.ext.asyncio import AsyncSession
from db import UserDB, CompanyDB, ScreenDB, ContainerDB, ItemDB, ProductCardDB, ImageDB
from db.session import get_db
from user.actions import __get_user_from_token
from navigations.actions import __check_permission_navigation
from utils.constants import EMPTY_UUID
from utils.money import Money, Percentage

from product_card.versioning import check_product_version

editor_router = APIRouter()


class ProductInput(BaseModel):
    version: Optional[conint(strict=True, ge=1)] = None
    id: Optional[UUID] = None
    title: constr(strip_whitespace=True, min_length=1, max_length=35)
    sub_title: constr(max_length=35) = ''
    header: constr(max_length=35) = ''
    description: constr(max_length=5000) = ''
    hint_header: constr(max_length=35) = ''
    hint_description: constr(max_length=35) = ''
    product_category: constr(max_length=35) = ''
    custom_product_category: constr(max_length=35) = ''
    product_release_type: constr(max_length=35) = ''
    allergens_list: constr(max_length=35) = ''
    quantity_system: constr(max_length=35) = ''
    tags: constr(max_length=35) = ''
    count_number: conint(ge=0, le=2147483647) = 0
    product_quantity: conint(ge=0, le=2147483647) = 0
    calorie_content: conint(ge=0, le=2147483647) = 0
    proteins: conint(ge=0, le=2147483647) = 0
    fats: conint(ge=0, le=2147483647) = 0
    carbohydrates: conint(ge=0, le=2147483647) = 0
    cooking_time: conint(ge=0, le=2147483647) = 0
    price: Money = 0
    cost_price: Money = 0
    cashback_perc: Percentage = 0
    bonuses_payment: bool = False
    single_product_type: bool = False
    is_sharpness: bool = False
    is_hotness: bool = False
    company_group_id: conint(ge=-1, le=2147483647) = -1
    image_product_id: UUID = EMPTY_UUID
    image_icon_id: UUID = EMPTY_UUID


def product_view(product):
    from decimal import Decimal
    fields = {col.name: getattr(product, col.name) for col in ProductCardDB.__table__.columns}
    return {**{key: format(value, '.2f') if isinstance(value, Decimal) else value for key, value in fields.items()},
            'id': product.product_card_id, 'image_id': product.image_product_id,
            'is_used': bool(product.is_used)}


@editor_router.put('/products')
async def save_product(company_id: UUID, body: ProductInput, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    await access(db, user, company_id)
    for image_id in (body.image_product_id, body.image_icon_id):
        if image_id != EMPTY_UUID and not await db.scalar(select(ImageDB.image_id).where(
                ImageDB.image_id == image_id, ImageDB.company_id == company_id, ImageDB.is_hidden.is_(False))):
            raise HTTPException(404, 'Image not found')
    obj = None
    if body.id:
        obj = await db.scalar(select(ProductCardDB).options(noload('*')).where(
            ProductCardDB.product_card_id == body.id, ProductCardDB.company_id == company_id, ProductCardDB.is_active.is_(True)).with_for_update())
        if obj is None:
            raise HTTPException(404, 'Product not found')
        check_product_version(body.version, obj.version)
        obj.version += 1
    if obj is None:
        obj = ProductCardDB(company_id=company_id, creator_id=user.user_id)
        db.add(obj)
    for key, value in body.dict(exclude={'id', 'version'}).items():
        setattr(obj, key, value)
    obj.updater_id = user.user_id
    await db.commit()
    return {'id': obj.product_card_id, 'version': obj.version}


@editor_router.delete('/products/{product_id}')
async def archive_product(product_id: UUID, company_id: UUID, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    await access(db, user, company_id)
    obj = await db.scalar(select(ProductCardDB).options(noload('*')).where(
        ProductCardDB.product_card_id == product_id, ProductCardDB.company_id == company_id).with_for_update())
    if obj is None:
        raise HTTPException(404, 'Product not found')
    obj.version += 1
    obj.is_active, obj.updater_id = False, user.user_id
    # Remove menu placements, never the product or historical order rows.
    company_containers = await containers(db, company_id)
    placements = (await db.execute(select(ItemDB).options(noload('*')).where(
        ItemDB.product_card_id == product_id,
        ItemDB.container_id.in_([c.container_id for c in company_containers])))).scalars().all()
    affected = {i.container_id for i in placements}
    for item in placements:
        await db.delete(item)
    affected_screens = {c.screen_id for c in company_containers if c.container_id in affected}
    for screen in await screens(db, company_id):
        if screen.screen_id in affected_screens:
            screen.editor_version += 1
    await db.commit()
    return {'status': 'archived'}


class Publication(BaseModel):
    is_active: Optional[StrictBool] = None
    is_visible: Optional[StrictBool] = None


def apply_publication(obj, body):
    # Older clients omitting flags must not republish hidden objects.
    for field in ('is_active', 'is_visible'):
        value = getattr(body, field)
        if value is not None:
            setattr(obj, field, value)


class Placement(Publication):
    id: Optional[UUID] = None
    product_id: UUID
    x: conint(ge=0, le=220)
    y: conint(ge=0, le=1860)


class CanvasContainer(Publication):
    id: Optional[UUID] = None
    title: constr(strip_whitespace=True, min_length=1, max_length=100)
    description: constr(max_length=5000) = ''
    x: conint(ge=0, le=70)
    y: conint(ge=0, le=1880)
    items: List[Placement] = Field(default_factory=list, max_items=300)


class CanvasInput(Publication):
    id: Optional[UUID] = None
    title: constr(strip_whitespace=True, min_length=1, max_length=100)
    description: constr(max_length=5000) = ''
    version: conint(ge=0) = 0
    grid: bool = False
    containers: List[CanvasContainer] = Field(default_factory=list, max_items=100)


@editor_router.put('/canvas')
async def save_canvas(company_id: UUID, body: CanvasInput, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    """Atomically persist a complete screen; stale editors cannot overwrite newer saves."""
    await access(db, user, company_id)
    ss = await screens(db, company_id)
    screen = next((s for s in ss if s.screen_id == body.id), None)
    if body.id and screen is None:
        raise HTTPException(404, 'Screen not found')
    if screen and screen.editor_version != body.version:
        raise HTTPException(409, 'Screen changed; reload before saving')
    cs = [c for c in await containers(db, company_id) if c.screen_id == body.id] if screen else []
    old_items = (await db.execute(select(ItemDB).options(noload('*')).where(
        ItemDB.container_id.in_([c.container_id for c in cs])))).scalars().all()
    products = set((await db.execute(select(ProductCardDB.product_card_id).where(
        ProductCardDB.company_id == company_id, ProductCardDB.is_active.is_(True)))).scalars())
    seen_containers, seen_items = set(), set()
    for container in body.containers:
        if body.grid:
            positions = [(item.x, item.y) for item in container.items]
            allowed = {(12+(index % 2)*152, 12+(index // 2)*152) for index in range(26)}
            if len(positions)>26 or len(set(positions))!=len(positions) or not set(positions).issubset(allowed):
                raise HTTPException(422, 'Items must occupy unique cells in a two-column grid')
        if container.id:
            if container.id in seen_containers or not any(c.container_id == container.id for c in cs):
                raise HTTPException(422, 'Invalid container')
            seen_containers.add(container.id)
        for item in container.items:
            if item.product_id not in products:
                raise HTTPException(404, 'Product not found')
            if item.id:
                if item.id in seen_items or not any(i.item_id == item.id and i.container_id == container.id and i.product_card_id == item.product_id for i in old_items):
                    raise HTTPException(422, 'Invalid placement')
                seen_items.add(item.id)
    if screen is None:
        screen = ScreenDB(company_id=company_id, creator_id=user.user_id,
                          screen_order_number=max([s.screen_order_number for s in ss], default=-1)+1)
        db.add(screen)
        await db.flush()
    screen.screen_title, screen.screen_sub_title = body.title, body.description
    apply_publication(screen, body)
    screen.updater_id = user.user_id
    screen.editor_version = (screen.editor_version or 0)+1
    for item in old_items:
        if item.item_id not in seen_items:
            await db.delete(item)
    await db.flush()
    for container in cs:
        if container.container_id not in seen_containers:
            await db.delete(container)
    for order, entry in enumerate(sorted(body.containers, key=lambda c: (c.y, c.x))):
        obj = next((c for c in cs if c.container_id == entry.id), None)
        if obj is None:
            obj = ContainerDB(screen_id=screen.screen_id)
            db.add(obj)
            await db.flush()
        apply_publication(obj, entry)
        obj.container_title, obj.container_sub_title = entry.title, entry.description
        obj.container_order_number, obj.layout_x, obj.layout_y = order, entry.x, entry.y
        for row, position in enumerate(sorted(entry.items, key=lambda i: (i.y, i.x))):
            item = next((i for i in old_items if i.item_id == position.id), None)
            if item is None:
                item = ItemDB(container_id=obj.container_id, product_card_id=position.product_id)
                db.add(item)
            apply_publication(item, position)
            item.layout_x, item.layout_y = position.x, position.y
            item.item_row_order, item.item_column_order = ((position.y-12)//152, (position.x-12)//152) if body.grid else (row, 0)
    await db.commit()
    return {'id': screen.screen_id, 'version': screen.editor_version}


class GroupInput(BaseModel):
    id: Optional[UUID] = None
    title: constr(strip_whitespace=True, min_length=1, max_length=100)
    description: constr(max_length=5000) = ''
    order: conint(ge=0, le=10000) = 0
    parent_id: Optional[UUID] = None


class ItemInput(BaseModel):
    product_version: Optional[conint(strict=True, ge=1)] = None
    id: Optional[UUID] = None
    container_id: UUID
    product_id: Optional[UUID] = None
    title: constr(strip_whitespace=True, min_length=1, max_length=35)
    description: constr(max_length=5000) = ''
    price: Money
    image_id: UUID = EMPTY_UUID
    row: conint(ge=0, le=10000) = 0
    column: conint(ge=0, le=10) = 0


async def access(db, user, company_id):
    if not await __check_permission_navigation(user_id=user.user_id, session=db, company_id=company_id):
        raise HTTPException(403, 'Forbidden')
    # Serialize editor writes in a company, including uniqueness checks for positions.
    company = await db.scalar(select(CompanyDB).options(noload('*')).where(
        CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True)).with_for_update())
    if company is None:
        raise HTTPException(404, 'Company not found')


async def screens(db, company_id):
    return (await db.execute(select(ScreenDB).options(noload('*')).where(ScreenDB.company_id == company_id))).scalars().all()


async def containers(db, company_id):
    return (await db.execute(select(ContainerDB).options(noload('*')).join(ScreenDB,
        ContainerDB.screen_id == ScreenDB.screen_id).where(ScreenDB.company_id == company_id))).scalars().all()


@editor_router.get('')
async def read_editor(company_id: UUID, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    await access(db, user, company_id)
    ss, cs = await screens(db, company_id), await containers(db, company_id)
    items = (await db.execute(select(ItemDB).options(noload('*')).where(
        ItemDB.container_id.in_([c.container_id for c in cs])))).scalars().all()
    products = (await db.execute(select(ProductCardDB).options(noload('*')).where(
        ProductCardDB.company_id == company_id, ProductCardDB.is_active.is_(True)))).scalars().all()
    return {
        'screens': [dict(id=s.screen_id, title=s.screen_title, description=s.screen_sub_title, order=s.screen_order_number, version=s.editor_version, is_active=s.is_active, is_visible=s.is_visible) for s in ss],
        'containers': [dict(id=c.container_id, parent_id=c.screen_id, title=c.container_title, description=c.container_sub_title, order=c.container_order_number, x=c.layout_x, y=c.layout_y, is_active=c.is_active, is_visible=c.is_visible) for c in cs],
        'items': [dict(id=i.item_id, container_id=i.container_id, product_id=i.product_card_id, row=i.item_row_order, column=i.item_column_order, x=i.layout_x, y=i.layout_y, is_active=i.is_active, is_visible=i.is_visible) for i in items],
        'products': [product_view(p) for p in products],
    }


@editor_router.put('/screens')
async def save_screen(company_id: UUID, body: GroupInput, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    await access(db, user, company_id)
    rows = await screens(db, company_id)
    obj = next((s for s in rows if s.screen_id == body.id), None)
    if body.id and obj is None:
        raise HTTPException(404, 'Screen not found')
    if any(s.screen_order_number == body.order and s.screen_id != body.id for s in rows):
        raise HTTPException(409, 'Position already occupied')
    if obj is None:
        obj = ScreenDB(company_id=company_id, creator_id=user.user_id)
        db.add(obj)
    obj.screen_title, obj.screen_sub_title, obj.screen_order_number = body.title, body.description, body.order
    obj.updater_id = user.user_id
    await db.commit()
    return {'id': obj.screen_id}


@editor_router.put('/containers')
async def save_container(company_id: UUID, body: GroupInput, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    await access(db, user, company_id)
    if not any(s.screen_id == body.parent_id for s in await screens(db, company_id)):
        raise HTTPException(404, 'Screen not found')
    rows = await containers(db, company_id)
    obj = next((c for c in rows if c.container_id == body.id), None)
    if body.id and obj is None:
        raise HTTPException(404, 'Container not found')
    if any(c.screen_id == body.parent_id and c.container_order_number == body.order and c.container_id != body.id for c in rows):
        raise HTTPException(409, 'Position already occupied')
    if obj is None:
        obj = ContainerDB(screen_id=body.parent_id)
        db.add(obj)
    obj.screen_id = body.parent_id
    obj.container_title, obj.container_sub_title, obj.container_order_number = body.title, body.description, body.order
    await db.commit()
    return {'id': obj.container_id}


@editor_router.put('/items')
async def save_item(company_id: UUID, body: ItemInput, db: AsyncSession = Depends(get_db), user: UserDB = Depends(__get_user_from_token)):
    await access(db, user, company_id)
    cs = await containers(db, company_id)
    if body.container_id not in [c.container_id for c in cs]:
        raise HTTPException(404, 'Container not found')
    obj = None
    if body.id:
        obj = await db.scalar(select(ItemDB).options(noload('*')).where(
            ItemDB.item_id == body.id, ItemDB.container_id.in_([c.container_id for c in cs])))
        if obj is None:
            raise HTTPException(404, 'Item not found')
    occupied = select(ItemDB.item_id).where(ItemDB.container_id == body.container_id,
        ItemDB.item_row_order == body.row, ItemDB.item_column_order == body.column)
    if body.id:
        occupied = occupied.where(ItemDB.item_id != body.id)
    if await db.scalar(occupied):
        raise HTTPException(409, 'Position already occupied')
    if body.image_id != EMPTY_UUID and not await db.scalar(select(ImageDB.image_id).where(
            ImageDB.image_id == body.image_id, ImageDB.company_id == company_id, ImageDB.is_hidden.is_(False))):
        raise HTTPException(404, 'Image not found')
    product = None
    if body.product_id:
        product = await db.scalar(select(ProductCardDB).options(noload('*')).where(
            ProductCardDB.product_card_id == body.product_id, ProductCardDB.company_id == company_id,
            ProductCardDB.is_active.is_(True)).with_for_update())
        if product is None:
            raise HTTPException(404, 'Product not found')
        check_product_version(body.product_version, product.version)
        product.version += 1
    if product is None:
        product = ProductCardDB(company_id=company_id, creator_id=user.user_id)
        db.add(product)
    product.title, product.description, product.price = body.title, body.description, body.price
    product.image_product_id, product.updater_id = body.image_id, user.user_id
    await db.flush()
    if obj is None:
        obj = ItemDB()
        db.add(obj)
    obj.container_id, obj.product_card_id = body.container_id, product.product_card_id
    obj.item_row_order, obj.item_column_order = body.row, body.column
    await db.commit()
    return {'id': obj.item_id}
