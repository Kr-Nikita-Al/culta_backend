"""Local Culta backups; optional verified upload to a dedicated S3 bucket."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = Path('/Users/kropotov-na/Documents/Codex/2026-09-02/new-chat/backups/scheduled')
PODMAN = ['/opt/podman/bin/podman', '--connection', 'culta-clean']
FORMAT = 'culta-main-db-backup-v1'


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def database_config():
    engine = shlex.split(os.environ.get('BACKUP_CONTAINER_COMMAND', '')) or PODMAN
    container = os.environ.get('BACKUP_DB_CONTAINER', 'main_db').strip()
    user = os.environ.get('BACKUP_DB_USER', 'nikita').strip()
    database = os.environ.get('BACKUP_DB_NAME', 'main_db').strip()
    if any(not value or value.startswith('-') or '\x00' in value
           for value in (container, user, database)):
        raise RuntimeError('Invalid backup database configuration')
    return engine, container, user, database


def command(args, *, stage, **kwargs):
    engine, _, _, _ = database_config()
    result = subprocess.run(engine + args, stderr=subprocess.PIPE, timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError(stage)
    return result


def s3_config():
    names = ('BACKUP_S3_ENDPOINT_URL', 'BACKUP_S3_BUCKET', 'BACKUP_S3_ACCESS_KEY_ID', 'BACKUP_S3_SECRET_ACCESS_KEY')
    config = {name: os.environ.get(name, '').strip() for name in names}
    if not all(config.values()):
        raise RuntimeError('Backup S3 configuration is incomplete')
    from urllib.parse import urlparse
    url = urlparse(config['BACKUP_S3_ENDPOINT_URL'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise RuntimeError('Backup S3 endpoint must use HTTPS without credentials')
    if config['BACKUP_S3_BUCKET'] == os.environ.get('AWS_BUCKET_NAME'):
        raise RuntimeError('Backups require a separate bucket, not the images bucket')
    return config


def upload_verified(path, manifest, config):
    import boto3
    from botocore.config import Config
    client = boto3.client('s3', endpoint_url=config['BACKUP_S3_ENDPOINT_URL'],
        aws_access_key_id=config['BACKUP_S3_ACCESS_KEY_ID'],
        aws_secret_access_key=config['BACKUP_S3_SECRET_ACCESS_KEY'],
        region_name=os.environ.get('BACKUP_S3_REGION', 'ru-central1'),
        config=Config(signature_version='s3v4', connect_timeout=10, read_timeout=60,
                      retries={'max_attempts': 3, 'mode': 'standard'}))
    key = 'culta/main_db/' + path.parent.name + '/main_db.dump'
    bucket = config['BACKUP_S3_BUCKET']
    with path.open('rb') as stream:
        client.put_object(Bucket=bucket, Key=key, Body=stream, ContentLength=path.stat().st_size,
            IfNoneMatch='*', Metadata={'sha256': manifest['sha256']}, ContentType='application/octet-stream')
    response = client.get_object(Bucket=bucket, Key=key)
    digest = hashlib.sha256()
    count = 0
    try:
        for chunk in response['Body'].iter_chunks(chunk_size=1024 * 1024):
            count += len(chunk)
            digest.update(chunk)
    finally:
        response['Body'].close()
    if count != manifest['bytes'] or digest.hexdigest() != manifest['sha256']:
        raise RuntimeError('Uploaded backup checksum mismatch')
    return {'bucket': bucket, 'key': key, 'verified': True}


def prune_local(directory, keep, require_remote):
    """Only owned, verified archives; always retain at least two good copies."""
    candidates = []
    for folder in directory.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{32}', folder.name):
            continue
        try:
            manifest = json.loads((folder / 'manifest.json').read_text())
            archive = folder / 'main_db.dump'
            if (manifest.get('format') != FORMAT or not manifest.get('complete')
                    or archive.is_symlink() or not archive.is_file()
                    or (require_remote and not manifest.get('remote', {}).get('verified'))
                    or set(p.name for p in folder.iterdir()) != {'manifest.json', 'main_db.dump'}
                    or checksum(archive) != manifest.get('sha256')):
                continue
            candidates.append(folder)
        except (OSError, ValueError):
            continue
    for folder in sorted(candidates, reverse=True)[max(2, keep):]:
        (folder / 'main_db.dump').unlink()
        (folder / 'manifest.json').unlink()
        folder.rmdir()


def backup(directory, upload=False, keep=14):
    os.umask(0o077)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / '.backup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'already_running'}
        status = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running'}
        atomic_json(directory / 'last_run.json', status)
        try:
            config = s3_config() if upload else None
            _, container, user, database = database_config()
            size = int(command(['exec', container, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', user,
                '-d', database, '-Atc', 'SELECT pg_database_size(current_database())'],
                stage='Read database size', stdout=subprocess.PIPE).stdout)
            if shutil.disk_usage(directory).free < size * 2 + 100_000_000:
                raise RuntimeError('Insufficient free disk space')
            name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex
            folder = directory / name
            folder.mkdir(mode=0o700)
            archive = folder / 'main_db.dump'
            with archive.open('xb') as stream:
                command(['exec', container, 'pg_dump', '-U', user, '-d', database, '-Fc'],
                        stage='Create database dump', stdout=stream)
            with archive.open('rb') as stream:
                command(['exec', '-i', container, 'pg_restore', '--file=/dev/null'],
                        stage='Verify archive decoding', stdin=stream, stdout=subprocess.PIPE)
            manifest = {'format': FORMAT, 'created_at': status['started_at'], 'bytes': archive.stat().st_size,
                'sha256': checksum(archive), 'archive_verified': True, 'complete': False,
                'scope': 'Database data/schema, excludes global roles and S3 objects'}
            atomic_json(folder / 'manifest.json', manifest)
            if upload:
                manifest['remote'] = upload_verified(archive, manifest, config)
            manifest['complete'] = True
            atomic_json(folder / 'manifest.json', manifest)
            status.update(status='ok', archive=str(archive), remote_verified=bool(manifest.get('remote')))
            prune_local(directory, keep, require_remote=upload)
        except Exception as error:
            status.update(status='failed', error_type=type(error).__name__)
            if type(error) is RuntimeError:
                status['error'] = str(error)
            raise
        finally:
            status['finished_at'] = datetime.now(timezone.utc).isoformat()
            atomic_json(directory / 'last_run.json', status)
        return status


if __name__ == '__main__':
    from environs import Env
    Env.read_env(str(ROOT / '.env'))
    parser = argparse.ArgumentParser()
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--directory', type=Path, default=Path(os.environ.get('BACKUP_DIRECTORY') or DEFAULT_DIRECTORY))
    parser.add_argument('--keep', type=int, default=14)
    args = parser.parse_args()
    try:
        print(json.dumps(backup(args.directory, args.upload, args.keep)))
    except Exception:
        print('Backup failed; see last_run.json (credentials are omitted).', file=sys.stderr)
        sys.exit(1)
