from enum import Enum


class ServiceType(str, Enum):
    SELF_SERVICE = 'self_service'
    WAITER_SERVICE = 'waiter_service'
