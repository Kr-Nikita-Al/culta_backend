"""UTC clock evaluated at each database insert or update, never at import time."""
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)
