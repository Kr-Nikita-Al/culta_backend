from typing import List

from company.interface_response.get_company_response import GetCompanyResponse
from utils.base_model_response import BaseModelResponse


class GetAllCompanyResponse(BaseModelResponse):
    companies: List[GetCompanyResponse]
