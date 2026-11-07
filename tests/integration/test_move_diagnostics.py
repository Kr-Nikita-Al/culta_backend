from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from db import StorageMoveDB, ImageDB
from image import api_handlers as api

pytestmark = pytest.mark.integration


@pytest.fixture
def diagnostic(pg, monkeypatch):
    pg.client.app.include_router(api.image_router, prefix='/image')
    head = AsyncMock(return_value={})
    monkeypatch.setattr(api, 'S3Client', lambda: SimpleNamespace(get_object_metadata=head))
    return head


def seed(pg, *, company='company_a', status='pending', invalid=False):
    operation = uuid4()
    root = f"company_images/company_{pg.ids[company]}/"
    pair = {'source':root+'old/a.png', 'destination':root+'new/a.png'}
    if invalid: pair['destination'] = f"company_images/company_{pg.ids['company_b']}/a.png"
    with Session(pg.engine) as session, session.begin():
        session.add(StorageMoveDB(operation_id=operation, company_id=pg.ids[company], kind='image',
            source_key=pair['source'], destination_key=pair['destination'], copied_keys=[pair], status=status))
    return operation, pair


def test_pending_list_is_scoped_and_paginated(pg, diagnostic):
    first, _ = seed(pg)
    seed(pg)
    seed(pg, company='company_b')
    seed(pg, status='committed')
    params = {'company_id':str(pg.ids['company_a']), 'limit':1}
    result = pg.client.get('/image/pending_moves', params=params, headers=pg.headers())
    assert result.status_code == 200
    assert result.json()['total'] == 2
    assert len(result.json()['operations']) == 1
    second = pg.client.get('/image/pending_moves', params={**params, 'offset':1}, headers=pg.headers()).json()
    assert second['operations'][0]['operation_id'] != result.json()['operations'][0]['operation_id']
    diagnostic.assert_not_awaited()


@pytest.mark.parametrize('state', ['both_present', 'source_only', 'destination_only', 'neither_present', 'unavailable'])
def test_probe_reports_presence_without_mutating_operation(pg, diagnostic, state):
    operation, pair = seed(pg)
    with Session(pg.engine) as session, session.begin():
        session.add(ImageDB(image_id=uuid4(), company_id=pg.ids['company_a'],
            file_path=pair['source'].rsplit('/',1)[0]+'/', file_name='a.png'))
    async def head(key):
        if state == 'unavailable': raise HTTPException(503, 'Private details')
        present = state == 'both_present' or (state == 'source_only' and key == pair['source']) or (state == 'destination_only' and key == pair['destination'])
        return {key:10} if present else {}
    diagnostic.side_effect = head
    result = pg.client.get('/image/move_diagnostics', params={
        'company_id':str(pg.ids['company_a']), 'operation_id':str(operation)}, headers=pg.headers())
    assert result.status_code == 200
    report = result.json()
    assert report['objects'][0]['state'] == state
    assert report['objects'][0]['source_referenced'] is True
    assert report['objects'][0]['destination_referenced'] is False
    assert report['safe_to_delete'] is False and report['safe_to_retry'] is False
    assert 'Private details' not in result.text
    with Session(pg.engine) as session:
        assert session.scalar(select(StorageMoveDB.status).where(StorageMoveDB.operation_id == operation)) == 'pending'


def test_cross_company_and_client_access_never_calls_storage(pg, diagnostic):
    operation, _ = seed(pg, company='company_b')
    params = {'company_id':str(pg.ids['company_a']), 'operation_id':str(operation)}
    assert pg.client.get('/image/move_diagnostics', params=params, headers=pg.headers()).status_code == 404
    assert pg.client.get('/image/move_diagnostics', params=params, headers=pg.headers('client_a')).status_code == 403
    assert pg.client.get('/image/pending_moves', params=params, headers=pg.headers('client_a')).status_code == 403
    diagnostic.assert_not_awaited()


def test_invalid_manifest_does_not_probe_other_tenant(pg, diagnostic):
    operation, _ = seed(pg, invalid=True)
    result = pg.client.get('/image/move_diagnostics', params={
        'company_id':str(pg.ids['company_a']), 'operation_id':str(operation)}, headers=pg.headers())
    assert result.status_code == 200
    assert result.json()['objects'] == [{'state':'invalid_manifest'}]
    diagnostic.assert_not_awaited()


@pytest.mark.parametrize('params', [{'limit':51}, {'limit':0}, {'offset':-1}])
def test_bounds_are_validated(pg, diagnostic, params):
    result = pg.client.get('/image/pending_moves', params={
        'company_id':str(pg.ids['company_a']), **params}, headers=pg.headers())
    assert result.status_code == 422
    diagnostic.assert_not_awaited()
