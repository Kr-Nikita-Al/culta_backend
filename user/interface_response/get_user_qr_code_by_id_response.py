from utils.base_model_response import BaseModelResponse


class GetUserQrCodeResponse(BaseModelResponse):
    qr_code: str
