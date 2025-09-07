from environs import Env

env = Env()
Env.read_env()

# Обязательно указывается связка в url postgresql+asyncpg для асинхронного подключения к БД//логин:пароль@хост:порт/бд
ENV: int = env.str("ENV")
# Database settings
REAL_DATABASE_URL = env.str("REAL_DATABASE_URL")
# App settings
APP_PORT: int = env.int('APP_PORT')
# Super-admin priviliges
ACCESS_SUPER_ADMINS: list[str] = env.list("ACCESS_SUPER_ADMINS")
# Hashing settings
SECRET_KEY: str = env.str("SECRET_KEY")
ALGORITHM: str = env.str("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES: int = env.int("ACCESS_TOKEN_EXPIRE_MINUTES")
# S3 storage
AWS_BUCKET_NAME: int = env.str("AWS_BUCKET_NAME")
AWS_ACCESS_KEY_ID: int = env.str("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: int = env.str("AWS_SECRET_ACCESS_KEY")
# Yandex auth app
YANDEX_CLIENT_ID: str = env.str("YANDEX_CLIENT_ID")
YANDEX_CLIENT_SECRET: str = env.str("YANDEX_CLIENT_SECRET")
YANDEX_REDIRECT_URI: str = env.str("YANDEX_REDIRECT_URI")


