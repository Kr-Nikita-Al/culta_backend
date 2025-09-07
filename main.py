import uvicorn
from fastapi import FastAPI, APIRouter

from settings import ENV
from s3_directory import s3_directory_router
from settings import APP_PORT
from auth import login_router
from user import user_router
from company import company_router
from image import image_router
from navigations import item_router, container_router, screen_router
from product_card import product_card_router
from user_role import user_role_router
from utils.ping_api import service_router
from fastapi.middleware.cors import CORSMiddleware

#############################
# БЛОК ОПИСАНИЯ API ROUTES  #
#############################

# Создание приложения
app = FastAPI(title="culta_backend")

# Создаем основной роутер
main_api_router = APIRouter()

# Безопасная конфигурация для продакшена
allowed_origins = ["*"]

# Разрешить локальные домены для разработки
if ENV == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000"
    ])

# Настройки CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "X-Total-Count"],
    max_age=600  # Кешировать предварительные запросы 10 минут
)

# Добавляем роутеры моделей
main_api_router.include_router(service_router, prefix="/ping", tags=["ping"])
main_api_router.include_router(user_router, prefix="/user", tags=["user"])
main_api_router.include_router(user_role_router, prefix="/user_role", tags=["user_role"])
main_api_router.include_router(company_router, prefix="/company", tags=["company"])
main_api_router.include_router(product_card_router, prefix="/product_card", tags=["product_card"])
main_api_router.include_router(image_router, prefix="/image", tags=["image"])
main_api_router.include_router(s3_directory_router, prefix="/s3_directory", tags=["s3_directory"])
main_api_router.include_router(item_router, prefix="/item_navigation", tags=["item_navigation"])
main_api_router.include_router(container_router, prefix="/container_navigation", tags=["container_navigation"])
main_api_router.include_router(screen_router, prefix="/screen_navigation", tags=["screen_navigation"])
main_api_router.include_router(login_router, prefix="/login", tags=["login"])

# Добавляем роутер в приложение
app.include_router(main_api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)
