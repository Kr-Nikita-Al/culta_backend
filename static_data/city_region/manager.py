import json
from pathlib import Path
from typing import List, Dict

from static_data.city_region import CityResponse


class CityManager:
    _cities: List[CityResponse] = None
    _cities_by_region: Dict[str, List[str]] = None

    @classmethod
    def load_cities(cls, file_path: str = "data/cities.json"):
        """Загружает города из JSON файла"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл {file_path} не найден")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cls._cities = [CityResponse(**item) for item in data]
        # Дополнительно: группировка по регионам для быстрого доступа
        cls._cities_by_region = {}
        for city in cls._cities:
            if city.region not in cls._cities_by_region:
                cls._cities_by_region[city.region] = []
            cls._cities_by_region[city.region].append(city.city)

    @classmethod
    def get_all_cities(cls) -> List[CityResponse]:
        """Возвращает все города"""
        if cls._cities is None:
            raise RuntimeError("Города не загружены. Вызовите load_cities()")
        return cls._cities

    @classmethod
    def get_cities_by_region(cls, region: str) -> List[str]:
        """Возвращает города по региону"""
        if cls._cities_by_region is None:
            raise RuntimeError("Города не загружены. Вызовите load_cities()")
        return cls._cities_by_region.get(region, [])

    @classmethod
    def search_cities(cls, query: str) -> List[CityResponse]:
        """Поиск городов по названию"""
        if cls._cities is None:
            raise RuntimeError("Города не загружены. Вызовите load_cities()")
        query = query.lower().strip()
        results = []
        for city in cls._cities:
            if query in city.city.lower():
                results.append(city)
        return results
