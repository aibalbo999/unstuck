import hashlib
import json
import sqlite3

import pytest

from storage.report_storage import LocalFileStorage
from storage._local_file_operations import metadata_path


def fixture_bundle(tmp_path):
    storage = LocalFileStorage(tmp_path / "output")
    name = "2330_TW_v1_report_20261018_000000.html"
    from report_paths import report_storage_key_for_filename
    key = report_storage_key_for_filename(name)
    html = '<html><body><main class="main">品質 gate 有警示；NT$100.00</main></body></html>'.encode()
    storage.save_report(key, html, content_type="text/html")
    storage.save_report(key.replace('.html', '.md'), b'original markdown', content_type="text/markdown")
    storage.save_report(key.replace('.html', '.data.json'), b'{"content_credibility":{"status":"blocked"}}', content_type="application/json")
    db = tmp_path / "index.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE reports (output_dir TEXT, filename TEXT, html_hash TEXT, file_mtime REAL, pipeline_id TEXT, data_trust_json TEXT, analysis_text_stale INTEGER)")
        conn.execute("INSERT INTO reports VALUES (?,?,?,?,?,?,?)", (str(storage._root), name, hashlib.sha256(html).hexdigest(), 12345, 'v1', '{"status":"stale"}', 1))
    return storage, db, name, key, html


def test_migration_only_changes_html_and_its_checksum(tmp_path):
    from report_reader_migration import migrate_report
    from report_reader_assets import remove_reader
    storage, db, name, key, original = fixture_bundle(tmp_path)
    before = {item.key: storage.get_report(item.key).content for item in storage.list_reports()}
    with sqlite3.connect(db) as conn:
        row_before = conn.execute('SELECT * FROM reports').fetchone()
    original_mtime = (storage._root / key).stat().st_mtime_ns
    result = migrate_report(db, storage, name, expected_sha256=hashlib.sha256(original).hexdigest(), apply=True)
    assert result['status'] == 'updated'
    changed = storage.get_report(key).content
    assert remove_reader(changed.decode()).encode() == original
    assert (storage._root / key).stat().st_mtime_ns == original_mtime
    for other, content in before.items():
        if other != key:
            assert storage.get_report(other).content == content
    with sqlite3.connect(db) as conn:
        row_after = conn.execute('SELECT * FROM reports').fetchone()
    assert row_before[:2] == row_after[:2]
    assert row_before[3:] == row_after[3:]
    assert row_after[2] == hashlib.sha256(changed).hexdigest()
    assert json.loads(metadata_path(storage._root / key).read_text())['sha256'] == row_after[2]
    assert migrate_report(db, storage, name, apply=True)['status'] == 'unchanged'


def test_dry_run_is_read_only_and_stale_input_is_rejected(tmp_path):
    from report_reader_migration import migrate_report
    storage, db, name, key, original = fixture_bundle(tmp_path)
    assert migrate_report(db, storage, name)['status'] == 'ready'
    assert storage.get_report(key).content == original
    with pytest.raises(ValueError, match='changed'):
        migrate_report(db, storage, name, expected_sha256='0' * 64, apply=True)
    with pytest.raises(ValueError, match='assets changed'):
        migrate_report(db, storage, name, expected_after_sha256='0' * 64, apply=True)
    assert storage.get_report(key).content == original


def test_index_failure_restores_html_sidecar_and_mtime(tmp_path):
    from report_reader_migration import migrate_report
    storage, db, name, key, original = fixture_bundle(tmp_path)
    path = storage._root / key
    mtime = path.stat().st_mtime_ns
    metadata = metadata_path(path).read_bytes()
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TRIGGER deny_update BEFORE UPDATE ON reports BEGIN SELECT RAISE(FAIL,'test rejection'); END")
    with pytest.raises(sqlite3.IntegrityError):
        migrate_report(db, storage, name, apply=True)
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == mtime
    assert metadata_path(path).read_bytes() == metadata


def test_corrupt_checksum_is_not_silently_repaired(tmp_path):
    from report_reader_migration import migrate_report
    storage, db, name, key, original = fixture_bundle(tmp_path)
    metadata_path(storage._root / key).write_text('{"sha256":"broken"}')
    with pytest.raises(ValueError, match='checksum'):
        migrate_report(db, storage, name, apply=True)
    assert (storage._root / key).read_bytes() == original


def test_snapshot_race_refuses_html_update_without_recursive_storage_lock(tmp_path, monkeypatch):
    import report_reader_migration as migration
    storage, db, name, key, original = fixture_bundle(tmp_path)
    load = migration._reader_snapshot

    def change_after_read(*args):
        result = load(*args)
        storage.save_report(key.replace('.html', '.data.json'), b'{"changed":true}', content_type='application/json')
        return result

    monkeypatch.setattr(migration, '_reader_snapshot', change_after_read)
    with pytest.raises(ValueError, match='snapshot changed'):
        migration.migrate_report(db, storage, name, apply=True)
    assert storage.get_report(key).content == original
