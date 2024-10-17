from uuid import UUID

from pydantic import BaseModel


class DeleteCompanyResponse(BaseModel):
    deleted_company_id: UUID
