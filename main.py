from contextlib import asynccontextmanager

from order.websocket.api_handlers import order_websocket_router
from settings import ENV

import uvicorn
from fastapi import FastAPI, APIRouter

from order import order_router
from s3_directory import s3_directory_router
from settings import APP_PORT
from auth import login_router
from static_data.api_handlers import static_data_router
from static_data.city_region import CityManager
from user import user_router
from company import company_router
from image import image_router
from navigations import item_router, container_router, screen_router
from product_card import product_card_router
from user_role import user_role_router
from utils.ping_api import service_router
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup логика
    CityManager.load_cities("static_data/city_region/data.json")
    yield

# Создание приложения
app = FastAPI(title="culta_backend", lifespan=lifespan)

#############################
# БЛОК ОПИСАНИЯ API ROUTES  #
#############################

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
main_api_router.include_router(order_router, prefix="/order", tags=["order_router"])
main_api_router.include_router(order_websocket_router, prefix="/order_websocket_router", tags=["order_websocket_router"])
main_api_router.include_router(static_data_router, prefix="/static_data", tags=["static_data_router"])


# Добавляем роутер в приложение
app.include_router(main_api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)
