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
AWS_BUCKET_NAME: int = env.str("AWS_BUCKET_NAME")
AWS_ACCESS_KEY_ID: int = env.str("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY: int = env.str("AWS_SECRET_ACCESS_KEY")

