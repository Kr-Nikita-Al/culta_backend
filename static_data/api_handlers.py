from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from static_data.city_region import CitiesListResponse
from static_data.city_region import CityManager

static_data_router = APIRouter()


@static_data_router.get("/get_all_cities", response_model=CitiesListResponse)
async def get_all_cities(
        region: Optional[str] = Query(None, description="Фильтр по региону"),
        search: Optional[str] = Query(None, description="Поиск по названию города"),
):
    """
    Получить список всех городов России.
    Возможна фильтрация по региону и поиск по названию.
    """
    try:
        if search:
            # Поиск по названию
            cities = CityManager.search_cities(search)
        elif region:
            # Фильтрация по региону
            city_names = CityManager.get_cities_by_region(region)
            # Преобразуем в CityResponse
            all_cities = CityManager.get_all_cities()
            cities = [
                city for city in all_cities
                if city.region == region and city.city in city_names
            ]
        else:
            # Все города
            cities = CityManager.get_all_cities()
        return CitiesListResponse(cities=cities)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@static_data_router.get("/get_regions", response_model=List[str])
async def get_all_regions():
    """Получить список всех регионов"""
    try:
        # Собираем уникальные регионы
        cities = CityManager.get_all_cities()
        regions = sorted(set(city.region for city in cities))
        return regions
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
