"""Single role-aware transition policy used by REST and socket commands."""
from fastapi import HTTPException
from db import STATUS_TYPE as S

_WAITER = frozenset({(S.CREATED, S.CANCELED), (S.CREATED, S.COMPLETED),
                     (S.CREATED, S.CLOSED), (S.COMPLETED, S.CLOSED)})
_COOK = frozenset({(S.CREATED, S.PROCESSING), (S.CREATED, S.CANCELED),
                   (S.PROCESSING, S.COMPLETED)})
_MANAGER = _WAITER | _COOK
ROLE_TRANSITIONS = (("is_waiter", _WAITER), ("is_cook", _COOK),
                    ("is_admin", _MANAGER), ("is_owner", _MANAGER))


def can_transition(role, old_status, new_status):
    """Multiple company roles grant the union of their allowed transitions."""
    return any(getattr(role, attribute, False) and (old_status, new_status) in edges
               for attribute, edges in ROLE_TRANSITIONS)


def validate_transition(role, old_status, new_status, *, check_id=None):
    if not any(getattr(role, attribute, False) for attribute, _ in ROLE_TRANSITIONS):
        raise HTTPException(403, 'Forbidden')
    if old_status in (S.CLOSED, S.CANCELED):
        raise HTTPException(409, 'Order is closed or canceled')
    if not can_transition(role, old_status, new_status):
        raise HTTPException(422, 'Incorrect new status for update')
    if new_status == S.CLOSED and check_id is not None:
        raise HTTPException(409, 'Close the check through /check/close; preparation status is separate')
