from uuid import UUID
import datetime
from pydantic import EmailStr

from utils.base_model_response import BaseModelResponse


class GetCompanyResponse(BaseModelResponse):
    company_id: UUID
    company_name: str
    address: str
    phone: str
    email: EmailStr
    is_active: bool
    order_number: int
    main_screen_id: int
    group_id: int
    company_image: str
    company_icon: str
    age_limit: bool
    work_state: bool
    creator_id: UUID
    updater_id: UUID
    time_created: datetime.datetime
    time_updated: datetime.datetime
    start_time: datetime.time
    over_time: datetime.time
