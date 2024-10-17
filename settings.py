from envparse import Env


env = Env()

# Обязательно указывается связка в url postgresql+asyncpg для асинхронного подключения к БД//логин:пароль@хост:порт/бд
REAL_DATABASE_URL = env.str(
    "REAL_DATABASE_URL",
    default="postgresql+asyncpg://nikita:12345@0.0.0.0:5431/main_db",
)

APP_PORT: int = env.int('APP_PORT', default=8000)





