from email.policy import default

from envparse import Env


env = Env()

# Обязательно указывается связка в url postgresql+asyncpg для асинхронного подключения к БД//логин:пароль@хост:порт/бд
REAL_DATABASE_URL = env.str(
    "REAL_DATABASE_URL",
    default="postgresql+asyncpg://nikita:12345@127.0.0.1:5431/main_db",
)

APP_PORT: int = env.int('APP_PORT', default=8000)
SECRET_KEY: str = env.str("SECRET_KEY", default="secret_key")
ALGORITHM: str = env.str("ALGORITHM", default="HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = env.int("ACCESS_TOKEN_EXPIRE_MINUTES", default=1440*7)
# SENTRY_URL: str = env.str("SENTRY_URL", default = )




