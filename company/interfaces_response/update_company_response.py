from uuid import UUID

from pydantic import BaseModel


class UpdateCompanyResponse(BaseModel):
    updated_company_id: UUID
