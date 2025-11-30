from datetime import datetime, timedelta
from fastapi import HTTPException
from starlette import status

import qrcode
import io
import base64

from jose import jwt, JWTError

from settings import QR_SECRET_KEY, QR_ALGORITHM


def generate_jwt_qr_data(user_id: str, expires_minutes: int = 60) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = {
            'user_id': user_id,
            'iat': datetime.now(),
            'exp': datetime.now() + timedelta(minutes=expires_minutes),
            'type': 'qr_auth'
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