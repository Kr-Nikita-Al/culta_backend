"""Reference validation through real authorized PATCH endpoints."""
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from db import CompanyDB, ProductCardDB, ImageDB, ScreenDB
from utils.constants import EMPTY_UUID

pytestmark = pytest.mark.integration


@pytest.fixture
def refs(pg):
    ids = {key:uuid4() for key in ('image_a','image_b','screen_a','screen_b')}
    with Session(pg.engine) as session, session.begin():
        for suffix in ('a','b'):
            session.add(ImageDB(image_id=ids['image_'+suffix], company_id=pg.ids['company_'+suffix], file_name='test.jpg'))
            session.add(ScreenDB(screen_id=ids['screen_'+suffix], company_id=pg.ids['company_'+suffix]))
    return ids


@pytest.mark.parametrize('target,field,kind', [
    ('company','basic_screen_id','screen'), ('company','image_picture_id','image'),
    ('company','image_icon_id','image'), ('product_card','image_product_id','image'),
    ('product_card','image_icon_id','image'),
])
def test_scoped_reference_missing_foreign_valid_and_clear(pg, refs, target, field, kind):
    key = 'company_id' if target == 'company' else 'product_card_id'
    oid = pg.ids['company_a' if target == 'company' else 'product_a']
    model = CompanyDB if target == 'company' else ProductCardDB
    title = 'company_name' if target == 'company' else 'title'
    def patch(value, role='admin_a'):
        version = {}
        if target == 'product_card':
            with pg.engine.connect() as c:
                version = {'version': c.execute(select(ProductCardDB.version).where(ProductCardDB.product_card_id == oid)).scalar_one()}
        return pg.client.patch(f'/{target}/update_by_id', params={key:str(oid)},
            headers=pg.headers(role), json={field:str(value), title:'Updated', **version})
    for bad in (uuid4(), refs[kind+'_b'], 'not-a-uuid'):
        response = patch(bad)
        assert response.status_code == 422, response.text
        with pg.engine.connect() as c:
            row = c.execute(select(getattr(model,field),getattr(model,title)).where(getattr(model,key)==oid)).one()
            assert row[0] == EMPTY_UUID and row[1] != 'Updated'
    assert patch(refs[kind+'_a'],'admin_b').status_code == 403
    assert patch(refs[kind+'_a']).status_code == 200
    with pg.engine.connect() as c:
        assert c.execute(select(getattr(model,field)).where(getattr(model,key)==oid)).scalar_one() == refs[kind+'_a']
    assert patch(EMPTY_UUID).status_code == 200
    with pg.engine.connect() as c:
        assert c.execute(select(getattr(model,field)).where(getattr(model,key)==oid)).scalar_one() == EMPTY_UUID
