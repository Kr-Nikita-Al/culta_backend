from utils.base_model_response import BaseModelResponse


class GetStorageLimitsInCompanyResponse(BaseModelResponse):
    quota_count_images: int
    quota_storage_size: int
    used_count: int
    used_size: int
