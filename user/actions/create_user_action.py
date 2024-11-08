from sqlalchemy.ext.asyncio import AsyncSession

from user.model_dal import UserDAL
from user.interfaces_request.create_user_request import CreateUserRequest
from user.interfaces_response.create_user_response import CreateUserResponse
from utils.hashing import Hasher

async def _create_user(user_body: CreateUserRequest, session: AsyncSession) -> CreateUserResponse:
    async with session.begin():
        user_dal = UserDAL(session)
        user_db = await user_dal.create_user(
            name= user_body.user_name,
            surname = user_body.user_surname,
            phone=user_body.phone,
            email=user_body.email,
            hashed_password = Hasher.get_password_hash(user_body.password),
            # roles = [PortalRole.ROLE_PORTAL_USER,],
        )
        return CreateUserResponse(
            user_id=user_db.company_id,
            user_name=user_db.company_name,
            user_surname=user_db.company_name,
            phone=user_db.phone,
            email=user_db.email,
            is_active=user_db.is_active,
            creator_id=user_db.creator_id,
            updater_id=user_db.updater_id,
            time_created=user_db.time_created,
            time_updated=user_db.time_updated
        )
