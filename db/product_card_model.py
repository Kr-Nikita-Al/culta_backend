from utils.timestamps import utc_now
from decimal import Decimal
from datetime import datetime
import uuid
from sqlalchemy import Column, ForeignKey, Integer, DateTime, String, Boolean, Numeric, CheckConstraint, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, column_property
from db.item_model import ItemDB
from db.container_model import ContainerDB
from db.screen_model import ScreenDB

from db.base_model import Base
from utils.constants import EMPTY_UUID

###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class ProductCardDB(Base):
    __tablename__ = 'product_card'
    product_card_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    version = Column(Integer, nullable=False, default=1, server_default='1')

    # Properties
    title = Column(String(35), default='')
    sub_title = Column(String(35), default='')
    header = Column(String(35), default='')
    description = Column(String(), default='')
    hint_header = Column(String(35), default='')
    hint_description = Column(String(35), default='')
    product_category = Column(String(35), default='')
    custom_product_category = Column(String(35), default='')
    product_release_type = Column(String(35), default='')
    allergens_list = Column(String(35), default='')
    quantity_system = Column(String(35), default='')
    tags = Column(String(35), default='')

    count_number = Column(Integer, default=0)
    price = Column(Numeric(18, 2), CheckConstraint('price >= 0 AND price <= 9999999999999999.99', name='ck_product_card_price_range'), default=Decimal('0.00'))
    cost_price = Column(Numeric(18, 2), CheckConstraint('cost_price >= 0 AND cost_price <= 9999999999999999.99', name='ck_product_card_cost_price_range'), default=Decimal('0.00'))
    cashback_perc = Column(Numeric(5, 2), CheckConstraint('cashback_perc >= 0 AND cashback_perc <= 100', name='ck_product_card_cashback_perc_range'), default=Decimal('0.00'))
    product_quantity = Column(Integer, default=0)
    calorie_content = Column(Integer, default=0)
    proteins = Column(Integer, default=0)
    fats = Column(Integer, default=0)
    carbohydrates = Column(Integer, default=0)
    cooking_time = Column(Integer, default=0)

    bonuses_payment = Column(Boolean, default=False)
    single_product_type = Column(Boolean, default=False)
    is_sharpness = Column(Boolean, default=False)
    is_hotness = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Connection fields
    company_id = Column(ForeignKey('company.company_id'), primary_key=True, nullable=False)
    # Derived from current menu placements, not historical orders or a mutable flag.
    is_used = column_property(select(ItemDB.item_id).join(
        ContainerDB, ItemDB.container_id == ContainerDB.container_id).join(
        ScreenDB, ContainerDB.screen_id == ScreenDB.screen_id).where(
        ItemDB.product_card_id == product_card_id,
        ScreenDB.company_id == company_id).correlate_except(ItemDB, ContainerDB, ScreenDB).exists())
    company_group_id = Column(Integer, default=-1)
    image_product_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    image_icon_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)

    # Relationships
    item = relationship("ItemDB", back_populates="product_card_info", lazy="joined")
    order_items = relationship("OrderProductAssociationDB", back_populates="product_info")

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=utc_now)
    time_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
