from datetime import datetime
import uuid

from sqlalchemy import Column, ForeignKey, Integer, DateTime, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base_model import Base
from utils.constants import EMPTY_UUID


###########################
# БЛОК ОПИСАНИЯ МОДЕЛИ БД #
###########################


class ProductCardDB(Base):
    __tablename__ = 'product_card'

    product_card_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Properties
    title = Column(String(35), default='')
    sub_title = Column(String(35), default='')
    header = Column(String(35), default='')
    description = Column(String(35), default='')
    hint_header = Column(String(35), default='')
    hint_description = Column(String(35), default='')
    product_category = Column(String(35), default='')
    custom_product_category = Column(String(35), default='')
    product_release_type = Column(String(35), default='')
    allergens_list = Column(String(35), default='')
    quantity_system = Column(String(35), default='')
    tags = Column(String(35), default='')

    count_number = Column(Integer, default=0)
    price_field_1 = Column(Integer, default=0)
    price_field_2 = Column(Integer, default=0)
    cost_price_field_1 = Column(Integer, default=0)
    cost_price_field_2 = Column(Integer, default=0)
    cashback_field_1 = Column(Integer, default=0)
    cashback_field_2 = Column(Integer, default=0)
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

    # Connection fields
    company_id = Column(ForeignKey('company.company_id'), primary_key=True)
    # company = relationship("CompanyDB", backref="product_cards")
    company_group_id = Column(Integer, default=-1)
    product_image_id = Column(Integer, default=EMPTY_UUID)
    icon_image_id = Column(Integer, default=EMPTY_UUID)

    # Technical fields
    creator_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    updater_id = Column(UUID(as_uuid=True), default=EMPTY_UUID)
    time_created = Column(DateTime(timezone=True), default=datetime.now())
    time_updated = Column(DateTime(timezone=True), default=datetime.now(), onupdate=datetime.now())
