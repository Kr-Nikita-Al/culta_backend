from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from utils.constants import EMPTY_UUID, PortalRole
from user.actions.qr_code_action import __generate_qr_base64

from user.interface_request import CreateUserRequest
from user.model_dal import UserDAL
from user.interface_response import CreateUserResponse
from utils.hashing import Hasher


async def __create_user(user_body: CreateUserRequest, session: AsyncSession) -> CreateUserResponse:
    from user_role.model_dal import UserRoleDAL
    password_hash = await Hasher.hash_async(user_body.password)
    async with session.begin():
        user_dal = UserDAL(session)
        user_db = await user_dal.create_user(
            name=user_body.name,
            surname=user_body.surname,
            phone=user_body.phone,
            email=user_body.email,
            hashed_password=password_hash,
        )
        await UserRoleDAL(session).grant_user_role(user_db.user_id, EMPTY_UUID,
            PortalRole.PORTAL_ROLE_USER, user_db.user_id)
        user_db.qr_code = await asyncio.to_thread(__generate_qr_base64, str(user_db.user_id))
        await session.flush()
        return CreateUserResponse(
            user_id=user_db.user_id,
            name=user_db.name,
            surname=user_db.surname,
            phone=user_db.phone,
            email=user_db.email,
            is_active=user_db.is_active,
            creator_id=user_db.creator_id,
            updater_id=user_db.updater_id,
            time_created=user_db.time_created,
            time_updated=user_db.time_updated
        )
