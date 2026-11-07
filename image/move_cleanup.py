"""Delete only exact, unreferenced source versions of committed operations."""
import asyncio
import logging
from fastapi import HTTPException
from sqlalchemy import select, func
from botocore.exceptions import BotoCoreError, ClientError
from db import CompanyDB, ImageDB, StorageMoveDB
from image.move_diagnostics import valid_pair

logger = logging.getLogger(__name__)


async def cleanup_move(session, company_id, operation_id, storage):
    report = {'deleted':0, 'already_absent':0, 'skipped':0, 'unavailable':False}
    async with session.begin():
        company = await session.scalar(select(CompanyDB.company_id).where(
            CompanyDB.company_id == company_id, CompanyDB.is_active.is_(True)).with_for_update())
        if company is None:
            raise HTTPException(404, 'Company not found')
        # New images take the company lock; edits take image locks. Never delete
        # while any image path could be moving into the old key.
        images = (await session.execute(select(ImageDB.image_id, ImageDB.file_path, ImageDB.file_name)
            .where(ImageDB.company_id == company_id).with_for_update(skip_locked=True))).all()
        count = await session.scalar(select(func.count()).select_from(ImageDB).where(ImageDB.company_id == company_id))
        if len(images) != count:
            return {**report, 'busy':True}
        row = await session.scalar(select(StorageMoveDB).where(StorageMoveDB.company_id == company_id,
            StorageMoveDB.operation_id == operation_id).with_for_update())
        if row is None:
            raise HTTPException(404, 'Operation not found')
        if row.status != 'committed':
            return {**report, 'pending':True}
        references = {image.file_path + image.file_name for image in images}
        pending = (await session.scalars(select(StorageMoveDB.copied_keys).where(
            StorageMoveDB.company_id == company_id, StorageMoveDB.status == 'pending'))).all()
        protected = {(pair.get('source'), pair.get('source_version'))
            for manifest in pending for pair in manifest if isinstance(pair, dict)}
        root = f'company_images/company_{company_id}/'
        entries = [dict(pair) for pair in row.copied_keys]
        candidates = []
        for pair in entries:
            if pair.get('source_cleanup') in ('deleted', 'already_absent'):
                continue
            if (not valid_pair(row, pair, root) or pair['source'] == pair['destination']
                    or pair['source'] in references or (pair['source'], pair.get('source_version')) in protected
                    or any(not isinstance(pair.get(k), str) or pair[k] in ('', 'null')
                           for k in ('source_version', 'destination_version'))):
                report['skipped'] += 1
                continue
            candidates.append(pair)
        if not candidates:
            return report
        try:
            async with asyncio.timeout(10):
                if not await storage.versioning_enabled():
                    return {**report, 'versioning_disabled':True}
                for pair in candidates[:10]:
                    # Keep the source unless the exact successful copy survives.
                    target = await storage.get_version_metadata(pair['destination'], pair['destination_version'])
                    if not target or target['version_id'] != pair['destination_version']:
                        report['skipped'] += 1
                        continue
                    source = await storage.get_version_metadata(pair['source'], pair['source_version'])
                    if source is None:
                        pair['source_cleanup'] = 'already_absent'
                        report['already_absent'] += 1
                    elif source['version_id'] != pair['source_version']:
                        report['skipped'] += 1
                    else:
                        await storage.delete_exact_version(pair['source'], pair['source_version'], company_id)
                        pair['source_cleanup'] = 'deleted'
                        report['deleted'] += 1
        except (HTTPException, BotoCoreError, ClientError, TimeoutError):
            # Uncertain delete results remain retryable; retry uses the same version.
            report['unavailable'] = True
        row.copied_keys = entries
        report['remaining'] = max(0, len(candidates) - 10)
    return report


async def try_cleanup_move(session, company_id, operation_id):
    from s3_directory.storage import S3Client
    try:
        return await cleanup_move(session, company_id, operation_id, S3Client())
    except Exception:
        # The move has already committed. Cleanup failure must not turn it into
        # a failed move in the UI. The journal remains available for explicit retry.
        logger.warning('Committed move retained for cleanup retry')
        return {'unavailable':True}
