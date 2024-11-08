import uvicorn
from fastapi import FastAPI, APIRouter

import settings
from company import company_router
from user import user_router
from auth import login_router
from image import image_router
from navigations import item_router, container_router, screen_router
from product_card import product_card_router
from utils.ping_api import service_router

#############################
# БЛОК ОПИСАНИЯ API ROUTES  #
#############################

# Создание приложения
app = FastAPI(title="culta_backend")

# Создаем основной роутер
main_api_router = APIRouter()

# Добавляем роутеры моделей
main_api_router.include_router(service_router, prefix="/ping", tags=["ping"])
main_api_router.include_router(company_router, prefix="/company", tags=["company"])
main_api_router.include_router(user_router, prefix="/user", tags=["user"])
main_api_router.include_router(login_router, prefix="/login", tags=["login"])
main_api_router.include_router(product_card_router, prefix="/product_card", tags=["product_card"])
main_api_router.include_router(image_router, prefix="/image", tags=["image"])
main_api_router.include_router(item_router, prefix="/item_navigation", tags=["item_navigation"])
main_api_router.include_router(container_router, prefix="/container_navigation", tags=["container_navigation"])
main_api_router.include_router(screen_router, prefix="/screen_navigation", tags=["screen_navigation"])

# Добавляем роутер в приложение
app.include_router(main_api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=settings.APP_PORT)