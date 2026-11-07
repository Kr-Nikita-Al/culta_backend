"""Read-only snapshots for operators; never authorize deletion or retry."""
import asyncio
from fastapi import HTTPException
from botocore.exceptions import BotoCoreError
from sqlalchemy import select, func
from db import StorageMoveDB, ImageDB


async def list_pending(session, company_id, offset=0, limit=20):
    async with session.begin():
        condition = (StorageMoveDB.company_id == company_id) & (StorageMoveDB.status == 'pending')
        total = await session.scalar(select(func.count()).select_from(StorageMoveDB).where(condition))
        rows = (await session.scalars(select(StorageMoveDB).where(condition)
            .order_by(StorageMoveDB.created_at, StorageMoveDB.operation_id).offset(offset).limit(limit))).all()
        return {'total':total, 'operations':[{
            'operation_id':row.operation_id, 'kind':row.kind, 'created_at':row.created_at,
            'source_key':row.source_key, 'destination_key':row.destination_key,
            'planned_count':len(row.copied_keys),
        } for row in rows], 'pending_may_be_in_progress':True}


def valid_pair(row, pair, root):
    if not isinstance(pair, dict):
        return False
    for key in ('source', 'destination'):
        value = pair.get(key)
        if (not isinstance(value, str) or not value.startswith(root) or '\\' in value
                or any(part in ('.', '..') for part in value.split('/'))):
            return False
    if row.kind == 'image':
        return pair['source'] == row.source_key and pair['destination'] == row.destination_key
    return (row.source_key.endswith('/') and row.destination_key.endswith('/')
        and pair['source'].startswith(row.source_key)
        and pair['destination'] == row.destination_key + pair['source'][len(row.source_key):])


async def inspect_move(session, company_id, operation_id, storage, offset=0, limit=20):
    async with session.begin():
        row = await session.scalar(select(StorageMoveDB).where(
            StorageMoveDB.company_id == company_id, StorageMoveDB.operation_id == operation_id))
        if row is None:
            raise HTTPException(404, 'Operation not found')
        status = row.status
        manifest = row.copied_keys
        pairs = manifest[offset:offset + limit]
        # Snapshot all current keys for this tenant; do not trust a historical prefix.
        refs = (await session.execute(select(ImageDB.file_path, ImageDB.file_name)
            .where(ImageDB.company_id == company_id))).all()
        referenced = {path + name for path, name in refs}
    deadline = asyncio.get_running_loop().time() + 10
    results = []
    root = f'company_images/company_{company_id}/'
    for pair in pairs:
        if not valid_pair(row, pair, root):
            results.append({'state':'invalid_manifest'})
            continue
        result = {**pair, 'source_referenced':pair['source'] in referenced,
                  'destination_referenced':pair['destination'] in referenced}
        try:
            found = []
            for key in (pair['source'], pair['destination']):
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError()
                metadata = await asyncio.wait_for(storage.get_object_metadata(key), timeout=min(2, remaining))
                found.append(key in metadata)
            result['state'] = {(True, True):'both_present', (True, False):'source_only',
                               (False, True):'destination_only', (False, False):'neither_present'}[tuple(found)]
        except (HTTPException, BotoCoreError, TimeoutError):
            result['state'] = 'unavailable'
        results.append(result)
    # Detect completion during the storage probe, but still label the response a snapshot.
    async with session.begin():
        latest = await session.scalar(select(StorageMoveDB.status).where(
            StorageMoveDB.company_id == company_id, StorageMoveDB.operation_id == operation_id))
    return {'operation_id':operation_id, 'status':latest, 'status_changed':latest != status,
            'snapshot_only':True, 'probe_scope':'current_key', 'safe_to_delete':False, 'safe_to_retry':False,
            'total':len(manifest), 'objects':results,
            'next_offset':offset + len(pairs) if offset + len(pairs) < len(manifest) else None}
