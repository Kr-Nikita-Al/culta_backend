"""Compatibility wrapper for the centralized transition policy."""
from order.status_policy import can_transition


async def __check_permissions_update_status(user_role_model, old_status, new_status):
    return can_transition(user_role_model, old_status, new_status)
