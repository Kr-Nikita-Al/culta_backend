"""Exhaustive role/status matrix, including legacy financial closure."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from db import STATUS_TYPE as S
from order.status_policy import can_transition, validate_transition


@pytest.mark.parametrize('role', ['is_waiter', 'is_cook', 'is_admin', 'is_owner',
                                  'is_hostess', 'is_super_admin', 'is_moderator', 'client'])
@pytest.mark.parametrize('old', list(S))
@pytest.mark.parametrize('new', list(S))
def test_role_transition_matrix(role, old, new):
    waiter = {('created', 'canceled'), ('created', 'completed'),
              ('created', 'closed'), ('completed', 'closed')}
    cook = {('created', 'processing'), ('created', 'canceled'), ('processing', 'completed')}
    edges = waiter if role == 'is_waiter' else cook if role == 'is_cook' else (
        waiter | cook if role in ('is_owner', 'is_admin') else set())
    assert can_transition(SimpleNamespace(**{role: True}), old, new) == ((old.value, new.value) in edges)


def test_combined_roles_and_linked_check():
    role = SimpleNamespace(is_cook=True, is_waiter=True)
    validate_transition(role, S.CREATED, S.PROCESSING)
    validate_transition(role, S.CREATED, S.COMPLETED)
    validate_transition(role, S.COMPLETED, S.CLOSED)
    with pytest.raises(HTTPException) as exc:
        validate_transition(role, S.COMPLETED, S.CLOSED, check_id=uuid4())
    assert exc.value.status_code == 409


@pytest.mark.parametrize('role,old,new,code', [
    (SimpleNamespace(), S.CLOSED, S.CREATED, 403),
    (SimpleNamespace(is_admin=True), S.CANCELED, S.CREATED, 409),
    (SimpleNamespace(is_admin=True), S.CREATED, S.CREATED, 422),
    (SimpleNamespace(is_waiter=True), S.CREATED, S.PROCESSING, 422),
])
def test_rejection_codes(role, old, new, code):
    with pytest.raises(HTTPException) as exc:
        validate_transition(role, old, new)
    assert exc.value.status_code == code
