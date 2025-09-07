import uuid
from enum import Enum

from settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

EMPTY_UUID = uuid.UUID(int=0)
EMPTY_PHONE = '89999999999'


class PortalRole(str, Enum):
    PORTAL_ROLE_SUPER_ADMIN = 'PORTAL_ROLE_SUPER_ADMIN'
    PORTAL_ROLE_ADMIN = 'PORTAL_ROLE_ADMIN'
    PORTAL_ROLE_MODERATOR = 'PORTAL_ROLE_MODERATOR'

    PORTAL_ROLE_USER = 'PORTAL_ROLE_USER'


# S3Storage

class BASE_STORAGE_DIRECTORY:
    USER = 'user_images/'
    COMPANY = 'company_images/'


CONFIG_S3CLIENT = {
    "endpoint_url": 'https://storage.yandexcloud.net',
    "aws_access_key_id": AWS_ACCESS_KEY_ID,
    "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
    "region_name": 'ru-central1'
}

LIMIT_FILE_SIZE = 2 * 1024 * 1024  # 2mb
LIMIT_DIRECTORY_SIZE = 100 * 1024 * 1024  # 100mb
IMAGE_ENLARGEMENTS = ['svg', 'pdf', 'eps', 'ai', 'cdr', 'png', 'jpeg', 'jpg', 'gif',
                      'raw', 'tiff', 'bmp', 'psd', 'webp', 'heif', 'avif']
