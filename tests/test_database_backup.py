import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from scripts import backup_database as backup


def test_server_backup_routes_all_database_commands(tmp_path, monkeypatch):
    monkeypatch.setenv('BACKUP_CONTAINER_COMMAND', 'docker --context production')
    monkeypatch.setenv('BACKUP_DB_CONTAINER', 'postgres-main')
    monkeypatch.setenv('BACKUP_DB_USER', 'backup_reader')
    monkeypatch.setenv('BACKUP_DB_NAME', 'culta')
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if 'pg_dump' in args:
            kwargs['stdout'].write(b'archive')
        return SimpleNamespace(returncode=0, stdout=b'1024')

    monkeypatch.setattr(backup.subprocess, 'run', run)
    assert backup.backup(tmp_path)['status'] == 'ok'
    assert all(args[:3] == ['docker', '--context', 'production'] for args in calls)
    assert calls[0][3:5] == ['exec', 'postgres-main']
    assert calls[1][3:] == ['exec', 'postgres-main', 'pg_dump', '-U', 'backup_reader', '-d', 'culta', '-Fc']
    assert calls[2][3:] == ['exec', '-i', 'postgres-main', 'pg_restore', '--file=/dev/null']


def test_invalid_source_fails_before_container_execution(tmp_path, monkeypatch):
    monkeypatch.setenv('BACKUP_DB_CONTAINER', '--privileged')
    run = Mock()
    monkeypatch.setattr(backup.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='Invalid backup database'):
        backup.backup(tmp_path)
    run.assert_not_called()


def make_copy(root, index, remote=True):
    folder = root / (f'202610{index:02}T030000Z-' + f'{index:032x}')
    folder.mkdir()
    archive = folder / 'main_db.dump'
    archive.write_bytes(b'backup')
    manifest = {'format': backup.FORMAT, 'complete': True, 'sha256': backup.checksum(archive),
                'remote': {'verified': remote}}
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    return folder


def test_retention_keeps_two_and_ignores_unverified_or_unowned(tmp_path):
    folders = [make_copy(tmp_path, i) for i in range(1, 5)]
    unverified = make_copy(tmp_path, 5, remote=False)
    corrupt = make_copy(tmp_path, 6)
    (corrupt / 'main_db.dump').write_bytes(b'corrupt')
    unrelated = tmp_path / 'manual-backup'
    unrelated.mkdir()
    backup.prune_local(tmp_path, keep=0, require_remote=True)
    assert not folders[0].exists() and not folders[1].exists()
    assert all(folder.exists() for folder in [*folders[2:], unverified, corrupt, unrelated])


def test_failure_preserves_archives_and_records_error(tmp_path, monkeypatch):
    existing = make_copy(tmp_path, 1)
    monkeypatch.setattr(backup, 'command', Mock(side_effect=RuntimeError('Read database size')))
    prune = Mock()
    monkeypatch.setattr(backup, 'prune_local', prune)
    with pytest.raises(RuntimeError):
        backup.backup(tmp_path)
    assert existing.exists()
    prune.assert_not_called()
    assert json.loads((tmp_path / 'last_run.json').read_text())['status'] == 'failed'


@pytest.mark.parametrize('case', ['missing', 'http', 'images'])
def test_external_config_requires_separate_https_bucket(monkeypatch, case):
    for name, value in {'BACKUP_S3_ENDPOINT_URL': 'https://storage.example.test',
                        'BACKUP_S3_BUCKET': 'backups', 'BACKUP_S3_ACCESS_KEY_ID': 'test',
                        'BACKUP_S3_SECRET_ACCESS_KEY': 'test'}.items():
        monkeypatch.setenv(name, value)
    if case == 'missing':
        monkeypatch.delenv('BACKUP_S3_SECRET_ACCESS_KEY')
    elif case == 'http':
        monkeypatch.setenv('BACKUP_S3_ENDPOINT_URL', 'http://storage.example.test')
    else:
        monkeypatch.setenv('AWS_BUCKET_NAME', 'backups')
    with pytest.raises(RuntimeError):
        backup.s3_config()


@pytest.mark.parametrize('valid', [True, False])
def test_uploaded_content_is_read_back_and_checked(tmp_path, monkeypatch, valid):
    import boto3
    archive = tmp_path / 'main_db.dump'
    archive.write_bytes(b'backup')
    body = SimpleNamespace(iter_chunks=lambda **kw: iter([b'backup' if valid else b'broken']), close=Mock())
    client = SimpleNamespace(put_object=Mock(), get_object=Mock(return_value={'Body': body}))
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: client)
    config = {'BACKUP_S3_ENDPOINT_URL': 'https://storage.example.test', 'BACKUP_S3_BUCKET': 'backups',
              'BACKUP_S3_ACCESS_KEY_ID': 'test', 'BACKUP_S3_SECRET_ACCESS_KEY': 'test'}
    manifest = {'bytes': 6, 'sha256': hashlib.sha256(b'backup').hexdigest()}
    if valid:
        assert backup.upload_verified(archive, manifest, config)['verified'] is True
    else:
        with pytest.raises(RuntimeError, match='checksum'):
            backup.upload_verified(archive, manifest, config)
    body.close.assert_called_once()
    assert client.put_object.call_args.kwargs['IfNoneMatch'] == '*'
