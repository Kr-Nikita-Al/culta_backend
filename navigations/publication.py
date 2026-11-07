"""Public navigation checks, separate from unrestricted staff editing reads."""
from fastapi import HTTPException
from sqlalchemy import select
from db import ScreenDB, ContainerDB, ItemDB, CompanyDB, ProductCardDB


def published(obj):
    return getattr(obj, 'is_active', True) and getattr(obj, 'is_visible', True)


async def require_published(db, kind, entity_id):
    query = select(ScreenDB.screen_id).join(CompanyDB, ScreenDB.company_id == CompanyDB.company_id)
    conditions = [CompanyDB.is_active.is_(True), ScreenDB.is_active.is_(True), ScreenDB.is_visible.is_(True)]
    if kind in ('container', 'item'):
        query = query.join(ContainerDB, ContainerDB.screen_id == ScreenDB.screen_id)
        conditions += [ContainerDB.is_active.is_(True), ContainerDB.is_visible.is_(True)]
    if kind == 'item':
        query = query.join(ItemDB, ItemDB.container_id == ContainerDB.container_id).join(ProductCardDB, ItemDB.product_card_id == ProductCardDB.product_card_id)
        conditions += [ItemDB.is_active.is_(True), ItemDB.is_visible.is_(True), ProductCardDB.is_active.is_(True), ProductCardDB.company_id == ScreenDB.company_id]
    key = {'screen': ScreenDB.screen_id, 'container': ContainerDB.container_id, 'item': ItemDB.item_id}[kind]
    async with db.begin():
        found = await db.scalar(query.where(key == entity_id, *conditions).limit(1))
    if found is None:
        raise HTTPException(404, 'Navigation element is not available')
