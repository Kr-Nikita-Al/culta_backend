"""Backup + isolated restore drill for the local Culta Podman database only.

Run with the project's Python environment. No source writes, no production
restore, no published ports. The backup contains private application data.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

import psycopg2
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
PODMAN = ['/opt/podman/bin/podman', '--connection', 'culta-clean']
BACKUPS = Path('/Users/kropotov-na/Documents/Codex/2026-09-02/new-chat/backups')
SOURCE_CONTAINER = 'main_db'
TABLES_SQL = "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2"
CATALOG_SQL = """SELECT json_build_object(
 'constraints', (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'),
 'indexes', (SELECT count(*) FROM pg_indexes WHERE schemaname='public'),
 'triggers', (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal))"""


def run(args, stage, **kwargs):
    result = subprocess.run(args, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        raise RuntimeError('Failed: ' + stage)
    return result


def capture(args, stage):
    return run(args, stage, stdout=subprocess.PIPE).stdout.decode().strip()


def sql(container, user, database, query):
    return capture(PODMAN + ['exec', container, 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
        '-U', user, '-d', database, '-Atc', query], 'read restored database')


def quoted_table(schema, table):
    return '.'.join('"' + value.replace('"', '""') + '"' for value in (schema, table))


class DigestWriter:
    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, data):
        self.digest.update(data.encode() if isinstance(data, str) else data)


def main():
    os.umask(0o077)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import settings
    url = make_url(settings.REAL_DATABASE_URL)
    if not (url.host in ('localhost', '127.0.0.1', '0.0.0.0') and url.port == 5431
            and url.database == 'main_db' and url.username == 'nikita'):
        raise RuntimeError('Refusing a non-local source database')
    source_image = capture(PODMAN + ['inspect', SOURCE_CONTAINER, '--format', '{{.Image}}'], 'inspect source image')
    token = uuid4().hex
    container = 'culta-restore-check-' + token
    database = 'culta_restore_' + token
    password = secrets.token_urlsafe(32)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = BACKUPS / ('culta-restore-drill-' + stamp + '-' + token[:8])
    folder.mkdir(parents=True, mode=0o700)
    report = {'created_at': stamp, 'complete': False, 'source_database': 'main_db',
              'scope': 'Database data and schema; excludes global roles, S3 and application secrets',
              'temporary_container_removed': False}
    report_path = folder / 'report.json'
    report_path.write_text(json.dumps(report, indent=2))
    try:
        connection = psycopg2.connect(url.set(drivername='postgresql', host='127.0.0.1').render_as_string(hide_password=False))
        try:
            connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_database_size(current_database())')
                size = cursor.fetchone()[0]
                if size > 256 * 1024 * 1024 or shutil.disk_usage(folder).free < size * 2 + 100_000_000:
                    raise RuntimeError('Restore drill exceeds local resource budget')
                cursor.execute('SELECT pg_export_snapshot()')
                snapshot = cursor.fetchone()[0]
                dump = folder / 'main_db.dump'
                with dump.open('xb') as output:
                    run(PODMAN + ['exec', SOURCE_CONTAINER, 'pg_dump', '-U', url.username,
                        '-d', url.database, '-Fc', '--snapshot=' + snapshot], 'snapshot backup', stdout=output)
                cursor.execute(TABLES_SQL)
                tables = cursor.fetchall()
                before = {}
                for schema, table in tables:
                    name = quoted_table(schema, table)
                    cursor.execute(f'SELECT count(*) FROM {name}')
                    count = cursor.fetchone()[0]
                    writer = DigestWriter()
                    cursor.copy_expert(f'COPY (SELECT row_to_json(t)::text FROM {name} t ORDER BY row_to_json(t)::text COLLATE "C") TO STDOUT', writer)
                    before[schema+'.'+table] = {'rows': count, 'sha256': writer.digest.hexdigest()}
                cursor.execute(CATALOG_SQL)
                catalog = cursor.fetchone()[0]
                cursor.execute('SELECT version_num FROM alembic_version')
                revision = cursor.fetchone()[0]
        finally:
            connection.close()
        report.update(backup_bytes=dump.stat().st_size,
                      backup_sha256=hashlib.sha256(dump.read_bytes()).hexdigest(), revision=revision)
        print('Snapshot backup and source checksums ready', flush=True)
        env = dict(os.environ, POSTGRES_PASSWORD=password)
        run(PODMAN + ['run', '-d', '--name', container, '--network', 'none',
            '--label', 'culta.restore-drill='+token, '--tmpfs', '/var/lib/postgresql/data:rw,size=1g',
            '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_USER=nikita', '-e', 'POSTGRES_DB='+database,
            source_image], 'create isolated PostgreSQL', env=env, stdout=subprocess.PIPE)
        for _ in range(60):
            result = subprocess.run(PODMAN + ['exec', container, 'pg_isready', '-U', 'nikita', '-d', database],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Temporary PostgreSQL startup timeout')
        with dump.open('rb') as source:
            run(PODMAN + ['exec', '-i', container, 'pg_restore', '--exit-on-error', '--single-transaction',
                '--no-owner', '--no-privileges', '-U', 'nikita', '-d', database],
                'restore backup', stdin=source, stdout=subprocess.PIPE)
        restored_tables = json.loads(sql(container, 'nikita', database,
            "SELECT json_agg(json_build_array(schemaname,tablename) ORDER BY schemaname,tablename) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')"))
        if restored_tables != [list(table) for table in tables]:
            raise RuntimeError('Restored table list differs')
        for schema, table in tables:
            name = quoted_table(schema, table)
            content = run(PODMAN + ['exec', container, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'nikita',
                '-d', database, '-Atc', f'COPY (SELECT row_to_json(t)::text FROM {name} t ORDER BY row_to_json(t)::text COLLATE "C") TO STDOUT'],
                'restored table fingerprint', stdout=subprocess.PIPE).stdout
            actual = {'rows': int(sql(container, 'nikita', database, f'SELECT count(*) FROM {name}')),
                      'sha256': hashlib.sha256(content).hexdigest()}
            if actual != before[schema+'.'+table]:
                raise RuntimeError('Restored data differs: '+schema+'.'+table)
        if json.loads(sql(container, 'nikita', database, CATALOG_SQL)) != catalog:
            raise RuntimeError('Restored schema object counts differ')
        report.update(tables=before, schema_objects=catalog, data_verified=True)
        print(f'Restored data verified: {len(tables)} tables', flush=True)
        run(PODMAN + ['build', '-t', 'culta-backend:restore-check', str(ROOT)], 'build current API image', stdout=subprocess.PIPE)
        restore_url = f'postgresql+asyncpg://nikita:{password}@127.0.0.1:5432/{database}'
        smoke = """import os, asyncio
import tests.conftest
os.environ['REAL_DATABASE_URL'] = os.environ['RESTORE_DATABASE_URL']
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url
config = Config('alembic.ini')
config.set_main_option('sqlalchemy.url', make_url(os.environ['RESTORE_DATABASE_URL']).set(drivername='postgresql+psycopg2').render_as_string(hide_password=False).replace('%', '%%'))
command.upgrade(config, 'head')
from db.session import engine
async def check():
    async with engine.connect() as connection:
        assert await connection.scalar(text('SELECT version_num FROM alembic_version')) == ScriptDirectory.from_config(config).get_current_head()
    await engine.dispose()
asyncio.run(check())
from main import app
from fastapi.testclient import TestClient
with TestClient(app) as client:
    assert client.get('/openapi.json').status_code == 200
print('RESTORE_API_OK')
"""
        result = run(PODMAN + ['run', '--rm', '--network', 'container:'+container,
            '-e', 'RESTORE_DATABASE_URL', 'culta-backend:restore-check', 'python', '-B', '-c', smoke],
            'restored database migration and API startup', env=dict(os.environ, RESTORE_DATABASE_URL=restore_url), stdout=subprocess.PIPE)
        if b'RESTORE_API_OK' not in result.stdout:
            raise RuntimeError('API verification marker missing')
        report.update(migrations_verified=True, api_startup_verified=True, complete=True)
    except Exception as error:
        report['error_type'] = type(error).__name__
        if type(error) is RuntimeError:
            report['error'] = str(error)  # Only the static stage errors raised above.
        raise
    finally:
        label = subprocess.run(PODMAN + ['inspect', container, '--format', '{{index .Config.Labels "culta.restore-drill"}}'],
                               capture_output=True, text=True)
        if label.returncode == 0 and label.stdout.strip() == token:
            run(PODMAN + ['rm', '-f', container], 'remove owned temporary container', stdout=subprocess.PIPE)
            report['temporary_container_removed'] = True
        report_path.write_text(json.dumps(report, indent=2))
    print('Verified restore report: '+str(report_path), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Exception messages from clients may include DSNs or row data.
        print('Restore drill failed ('+type(error).__name__+'); check the local report.', file=sys.stderr)
        sys.exit(1)
