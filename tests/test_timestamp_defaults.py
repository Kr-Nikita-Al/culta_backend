from datetime import datetime, timezone
import pytest
from db import UserDB, UserRoleDB, CompanyDB, ProductCardDB, OrderDB, ImageDB, ScreenDB


@pytest.mark.parametrize('model',[UserDB, UserRoleDB, CompanyDB, ProductCardDB, OrderDB, ImageDB, ScreenDB])
def test_timestamps_are_evaluated_when_written(model):
    for name in ('time_created','time_updated'):
        if name not in model.__table__.columns:
            continue
        column=model.__table__.columns[name]
        for default in (column.default,column.onupdate):
            if default is None:
                continue
            assert default.is_callable
            before=datetime.now(timezone.utc)
            value=default.arg(None)
            assert before <= value <= datetime.now(timezone.utc)
