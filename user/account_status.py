"""Global account access policy, shared by HTTP, login and WebSocket."""
from enum import Enum
from fastapi import HTTPException


class AccountStatus(str, Enum):
    pending = 'pending'
    confirmed = 'confirmed'
    blocked = 'blocked'
    deleted = 'deleted'


def require_confirmed(user):
    if not user.is_active or user.account_status in ('blocked', 'deleted'):
        raise HTTPException(403, 'Account unavailable')
    if user.account_status != 'confirmed':
        raise HTTPException(403, 'Email confirmation required')
