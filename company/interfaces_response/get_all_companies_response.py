from typing import List

from company.interfaces_response.get_company_response import GetCompanyResponse
from utils.base_model_response import BaseModelResponse


class GetAllCompanyResponse(BaseModelResponse):
    companies: List[GetCompanyResponse]
