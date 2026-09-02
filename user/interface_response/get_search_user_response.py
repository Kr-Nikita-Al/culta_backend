from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

from utils.base_model_response import BaseModelResponse


class UserSearchResponse(BaseModelResponse):
    user_id: int
    name: str
    time_created: datetime
    current_roles: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class PaginatedUsersResponse(BaseModelResponse):
    users: List[UserSearchResponse]
    total_count: int
    has_more: bool


class UserSimpleResponse(BaseModelResponse):
    user_id: UUID
    name: str
    time_created: datetime
    current_roles: List[Dict[str, Any]]

    class Config:
        from_attributes = True


class PaginatedUsersResponse(BaseModelResponse):
    users: List[UserSimpleResponse]
    page: int
    page_size: int
    total_users: int  # Общее количество пользователей ВО ВСЕЙ СИСТЕМЕ
    total_filtered: int  # Количество пользователей после применения фильтров
    total_pages: int  # Общее количество страниц
    has_next: bool
    has_previous: bool

    @classmethod
    def create(
            cls,
            users: List[UserSimpleResponse],
            page: int,
            page_size: int,
            total_users: int,
            total_filtered: int
    ) -> "PaginatedUsersResponse":
        """Фабричный метод для создания ответа"""
        total_pages = max(1, (total_filtered + page_size - 1) // page_size)
        has_next = page < total_pages
        has_previous = page > 1

        return cls(
            users=users,
            page=page,
            page_size=page_size,
            total_users=total_users,
            total_filtered=total_filtered,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )