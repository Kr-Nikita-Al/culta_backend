"""Real migrations and isolated schemas; never read the application's .env URL."""
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from auth.api_handlers import login_router
from db import CompanyDB, ProductCardDB, UserDB, UserRoleDB
from db.session import get_db
from order import api_handlers as rest
from order.websocket import api_handlers as ws
from order.websocket.manager import ConnectionManager
from utils.hashing import Hasher

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = 'integration-only-password'


@pytest.fixture(scope='session')
def integration_url():
    raw = os.environ.get('CULTA_INTEGRATION_DATABASE_URL')
    if not raw:
        pytest.fail('--integration requires CULTA_INTEGRATION_DATABASE_URL; see tests/README.md')
    url = make_url(raw)
    if (url.drivername != 'postgresql+asyncpg'
            or url.host not in ('127.0.0.1', 'localhost')
            or url.database != 'culta_integration_test'
            or url.username != 'culta_test' or url.query):
        pytest.fail('Refusing unsafe test URL: dedicated local culta_test/culta_integration_test required')
    return url


@pytest.fixture(scope='session')
def password_hash():
    return Hasher.get_password_hash(PASSWORD)


@pytest.fixture
def pg(integration_url, password_hash, monkeypatch, request):
    schema = 'culta_it_' + uuid4().hex
    sync_url = integration_url.set(drivername='postgresql+psycopg2')
    admin_engine = create_engine(sync_url, poolclass=NullPool)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    sync_engine = create_engine(sync_url, poolclass=NullPool,
                               connect_args={'options': f'-csearch_path={schema}'})
    async_engine = create_async_engine(integration_url, poolclass=NullPool,
        connect_args={'server_settings': {'search_path': schema, 'application_name': schema}})
    sessions = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        # Run the actual migration chain in the test schema, not metadata.create_all.
        config = Config(str(ROOT / 'alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'migrations'))
        migration_url = sync_url.update_query_dict({'options': f'-csearch_path={schema}'})
        config.set_main_option('sqlalchemy.url', migration_url.render_as_string(hide_password=False).replace('%', '%%'))
        revision = getattr(request, 'param', 'head')
        assert revision in ('head', 'a3bf3ac3dea2', 'd82e91b6a704', 'e49e37c102a8')
        command.upgrade(config, revision)

        ids = {key: uuid4() for key in ('company_a', 'company_b', 'admin_a', 'admin_b',
               'client_a', 'client_b', 'cook_a', 'waiter_a', 'product_a', 'product_a2', 'product_b', 'inactive')}
        if revision != 'head':
            seed_legacy(sync_engine, ids, password_hash)
        else:
            with Session(sync_engine) as session, session.begin():
                for suffix in ('a', 'b'):
                    session.add(CompanyDB(company_id=ids['company_' + suffix], company_name='Test ' + suffix,
                                          address='Test', phone='00000000000', email=f'{suffix}@example.test'))
                for role in ('admin_a', 'admin_b', 'client_a', 'client_b', 'cook_a', 'waiter_a'):
                    session.add(UserDB(user_id=ids[role], name='Test', surname=role, phone='00000000000',
                                       email=role + '@example.test', hashed_password=password_hash, account_status='confirmed'))
                session.flush()
                for role in ('admin_a', 'admin_b', 'cook_a', 'waiter_a'):
                    session.add(UserRoleDB(user_id=ids[role], company_id=ids['company_' + role[-1]],
                                          role='PORTAL_ROLE_' + role.split('_')[0].upper()))
                for key, company, price, active in [('product_a','a',250.5,True), ('product_a2','a',99.25,True),
                                                   ('product_b','b',100,True), ('inactive','a',50,False)]:
                    session.add(ProductCardDB(product_card_id=ids[key], company_id=ids['company_' + company],
                                              title=key, price=price, cost_price=10, is_active=active))

        async def test_db():
            async with sessions() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        manager = ConnectionManager()
        monkeypatch.setattr(rest, 'order_manager', manager)
        monkeypatch.setattr(ws, 'order_manager', manager)
        monkeypatch.setattr(ws, 'async_session', sessions)
        app = FastAPI()
        from company.admin_statistics import router as admin_statistics_router
        app.include_router(admin_statistics_router,prefix='/admin')
        app.include_router(login_router, prefix='/login')
        from user.api_handlers import user_router
        app.include_router(user_router, prefix='/user')
        from user_role.api_handlers import user_role_router
        app.include_router(user_role_router, prefix='/user_role')
        from navigations.editor import editor_router
        app.include_router(editor_router, prefix='/navigation_editor')
        from navigations import screen_router, container_router, item_router
        app.include_router(screen_router, prefix='/screen_navigation')
        app.include_router(container_router, prefix='/container_navigation')
        app.include_router(item_router, prefix='/item_navigation')
        app.include_router(rest.order_router, prefix='/order')
        from company.api_handlers import company_router
        from product_card.api_handlers import product_card_router
        app.include_router(company_router, prefix='/company')
        app.include_router(product_card_router, prefix='/product_card')
        from image.photo_api import photo_router
        app.include_router(photo_router, prefix='/photos')
        from checks.api_handlers import check_router
        app.include_router(check_router, prefix='/check')
        from reservations.api_handlers import reservation_router
        app.include_router(reservation_router, prefix='/reservations')
        app.include_router(ws.order_websocket_router, prefix='/ws')
        app.dependency_overrides[get_db] = test_db
        with TestClient(app) as client:
            tokens = {}

            def token(role):
                if role not in tokens:
                    response = client.post('/login/token', data={
                        'username': role + '@example.test', 'password': PASSWORD})
                    assert response.status_code == 200, response.text
                    tokens[role] = response.json()['access_token']
                return tokens[role]

            yield SimpleNamespace(client=client, ids=ids, token=token,
                headers=lambda role='admin_a': {'Authorization': 'Bearer ' + token(role)},
                engine=sync_engine, async_engine=async_engine, sessions=sessions, schema=schema,
                manager=manager, migration_config=config)
    finally:
        asyncio.run(async_engine.dispose())
        sync_engine.dispose()
        # Only the randomly generated schema created by this fixture is removed.
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def seed_legacy(engine, ids, password_hash):
    """Only columns present in the three tested historical revisions."""
    with engine.begin() as conn:
        for suffix in ('a', 'b'):
            conn.execute(text("""INSERT INTO company
                (company_id, company_name, address, phone, email, is_active,
                 bonus_payment_perc, bonus_accrual_perc)
                VALUES (:id, :name, 'Test', '00000000000', :email, true, 0, 0)"""),
                dict(id=ids['company_' + suffix], name='Test ' + suffix, email=suffix+'@example.test'))
        for role in ('admin_a', 'admin_b', 'client_a', 'client_b', 'cook_a', 'waiter_a'):
            conn.execute(text("""INSERT INTO "user"
                (user_id, name, surname, phone, email, hashed_password, is_active,
                 bonus_balance, time_created, time_updated)
                VALUES (:id, 'Test', :role, '00000000000', :email, :password, true, 500, now(), now())"""),
                dict(id=ids[role], role=role, email=role+'@example.test', password=password_hash))
        for role in ('admin_a', 'admin_b', 'cook_a', 'waiter_a'):
            conn.execute(text("""INSERT INTO user_role
                (relation_id, user_id, company_id, role, is_active)
                VALUES (:id, :uid, :cid, :role, true)"""),
                dict(id=uuid4(), uid=ids[role], cid=ids['company_'+role[-1]],
                     role='PORTAL_ROLE_'+role.split('_')[0].upper()))
        for key, price in [('product_a',250.5), ('product_a2',99.25)]:
            conn.execute(text("""INSERT INTO product_card
                (product_card_id, company_id, title, price, cost_price, is_active)
                VALUES (:id, :cid, :title, :price, 10, true)"""),
                dict(id=ids[key], cid=ids['company_a'], title=key, price=price))
        # Historical application defaults were Python-side, not database defaults.
        # Keep these explicit instead of depending on today's ORM schema.
        conn.execute(text("""UPDATE product_card SET
            sub_title='', header='', description='', hint_header='', hint_description='',
            product_category='', custom_product_category='', product_release_type='',
            allergens_list='', quantity_system='', tags='', count_number=0,
            cashback_perc=0, product_quantity=0, calorie_content=0, proteins=0,
            fats=0, carbohydrates=0, cooking_time=0, bonuses_payment=false,
            single_product_type=false, is_sharpness=false, is_hotness=false,
            company_group_id=-1, image_product_id=:empty, image_icon_id=:empty,
            creator_id=:empty, updater_id=:empty, time_created=now(), time_updated=now()"""),
            {'empty': '00000000-0000-0000-0000-000000000000'})
        ids['legacy_order'] = uuid4()
        conn.execute(text("""INSERT INTO orders
            (order_id, company_id, user_id, staff_id, status, price, bonus_transaction, comment, cocking_time,
             creator_id, updater_id, time_created, time_updated)
            VALUES (:id, :cid, :uid, :staff, 'CREATED', 798.75, 0, '', 0, :staff, :staff, now(), now())"""),
            dict(id=ids['legacy_order'], cid=ids['company_a'], uid=ids['client_a'], staff=ids['admin_a']))
        for key, quantity in [('product_a',2), ('product_a2',3)]:
            conn.execute(text("""INSERT INTO order_product_association
                (id, order_id, product_card_id, quantity) VALUES (:id, :oid, :pid, :qty)"""),
                dict(id=uuid4(), oid=ids['legacy_order'], pid=ids[key], qty=quantity))
