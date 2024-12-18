from environs import Env

env = Env()
Env.read_env()

# Обязательно указывается связка в url postgresql+asyncpg для асинхронного подключения к БД//логин:пароль@хост:порт/бд
REAL_DATABASE_URL = env.str("REAL_DATABASE_URL")
APP_PORT: int = env.int('APP_PORT')
ACCESS_SUPER_ADMINS: list[str] = env.list("ACCESS_SUPER_ADMINS")
SECRET_KEY: str = env.str("SECRET_KEY")
ALGORITHM: str = env.str("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES: int = env.int("ACCESS_TOKEN_EXPIRE_MINUTES")
