from typing import List

from image.interface_response import GetImageInterface
from utils.base_model_response import BaseModelResponse


class GetImagesInCompanyResponse(BaseModelResponse):
    images: List[GetImageInterface]
