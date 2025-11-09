from sqlalchemy.ext.asyncio import AsyncSession

from auth.intarface_response import CreateAuthAccountResponse
from auth.interface_request import CreateAuthAccountRequest
from auth.model_dal import AuthDal
from utils.hashing import Hasher


async def __create_auth_account(auth_account_body: CreateAuthAccountRequest, session: AsyncSession) -> CreateAuthAccountResponse:
    async with session.begin():
        auth_dal = AuthDal(session)
        auth_db = await auth_dal.create_auth_account(
            provider_user_id=auth_account_body.provider_user_id,
            provider=auth_account_body.provider,
            user_id=auth_account_body.user_id
        )
        return CreateAuthAccountResponse(
            auth_id=auth_db.auth_id,
            provider_user_id=auth_db.provider_user_id,
            provider=auth_db.provider,
            user_id=auth_db.user_id,
        )
