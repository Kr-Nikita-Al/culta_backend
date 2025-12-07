from datetime import datetime
from uuid import UUID

from utils.base_model_response import BaseModelResponse


class GetUserQrPayloadResponse(BaseModelResponse):
    user_id: UUID
    exp: datetime

