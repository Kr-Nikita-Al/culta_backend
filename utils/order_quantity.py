"""Creation quantities must fit PostgreSQL INTEGER without coercion."""
from pydantic import conint

MAX_ORDER_QUANTITY = 2_147_483_647
CreateQuantity = conint(strict=True, gt=0, le=MAX_ORDER_QUANTITY)
