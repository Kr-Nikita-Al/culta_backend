from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import time
from fastapi import HTTPException
from starlette import status

import qrcode
import io
import base64

from jose import jwt, JWTError

from settings import QR_SECRET_KEY, QR_ALGORITHM


def generate_jwt_qr_data(user_id: str, expires_minutes: int = 5) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        if not 0 < expires_minutes <= 5:
            raise ValueError('QR lifetime must be between zero and five minutes')
        now = datetime.now(timezone.utc)
        payload = {
            'user_id': str(UUID(user_id)),
            'iat': now,
            'exp': now + timedelta(minutes=expires_minutes),
            'type': 'client_identity',
            'aud': 'culta:client-identity',
            'jti': str(uuid4()),
        }
        return jwt.encode(payload, QR_SECRET_KEY, algorithm=QR_ALGORITHM)
    except JWTError:
        raise credentials_exception


def __generate_qr_base64(user_id: str) -> str:
    # Генерируем подписанные данные
    qr_data = generate_jwt_qr_data(user_id)
    # Создаем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Конвертируем в base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


async def __verify_qr_token(qr_token: str) -> dict:
    """Верифицирует JWT токен из QR-кода"""
    try:
        payload = jwt.decode(
            qr_token,
            QR_SECRET_KEY,
            algorithms=[QR_ALGORITHM],
            audience='culta:client-identity',
            options={'require_exp': True, 'require_iat': True, 'require_aud': True, 'require_jti': True},
        )
        if payload.get('type') != 'client_identity':
            raise ValueError('Wrong purpose')
        if not isinstance(payload.get('user_id'), str) or not isinstance(payload.get('jti'), str):
            raise ValueError('Invalid identifier')
        UUID(payload['user_id'])
        UUID(payload['jti'])
        issued, expires = payload['iat'], payload['exp']
        if (type(issued) is not int or type(expires) is not int or
                not 0 < expires-issued <= 300 or issued > time.time() or expires <= time.time()):
            raise ValueError('Invalid lifetime')
        return payload
    except (JWTError, ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired QR code"
        )
