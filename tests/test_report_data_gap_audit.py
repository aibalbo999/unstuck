"""Gap inventory must remain read-only and must not hide a broken latest report."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_report_data_gaps import audit
from report_paths import report_storage_key_for_filename
from storage.report_storage import LocalFileStorage


def reports(tmp_path):
    storage = LocalFileStorage(tmp_path / 'output')
    db = tmp_path / 'index.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE reports(output_dir TEXT, filename TEXT, ticker TEXT, pipeline_id TEXT, timestamp TEXT)')
        for mode, day in [('v4', '01'), ('v4', '02'), ('v1', '02')]:
            name = f'2330_TW_{mode}_report_202610{day}_000000.html'
            key = report_storage_key_for_filename(name)
            storage.save_report(key, b'<html>original</html>', content_type='text/html')
            value = {'pipeline': mode, 'source_audit': [{'source': 'recent_catalysts', 'provider': 'news',
                'status': 'error', 'error_kind': 'cooldown', 'record_count': 0}],
                'rerun_context': {'parsed': {'trade_setup': {'trade_direction': 'Neutral', 'entry_zone': 'N/A'}}}}
            storage.save_report(key.replace('.html', '.data.json'), json.dumps(value).encode(), content_type='application/json')
            conn.execute('INSERT INTO reports VALUES(?,?,?,?,?)', (str(storage._root), name, '2330.TW', mode, f'2026-10-{day}'))
    return storage, db


def test_audit_only_reads_latest_stock_modes_and_preserves_all_saved_bytes(tmp_path):
    storage, db = reports(tmp_path)
    before = {item.key: storage.get_report(item.key).content for item in storage.list_reports()}
    db_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    result = audit(db, storage._root)
    assert result['indexed_reports'] == 3 and result['reports_checked'] == 2
    assert result['modes'] == {'v4': 1, 'v1': 1}
    assert not result['errors']
    assert result['source_causes'][0]['error_kind'] == 'cooldown'
    assert all(storage.get_report(key).content == raw for key, raw in before.items())
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_hash


def test_invalid_latest_snapshot_is_reported_not_replaced_with_an_older_success(tmp_path):
    storage, db = reports(tmp_path)
    name = '2330_TW_v4_report_20261002_000000.html'
    key = report_storage_key_for_filename(name).replace('.html', '.data.json')
    storage.save_report(key, b'[]', content_type='application/json')
    result = audit(db, storage._root)
    assert result['reports_checked'] == 1
    assert result['errors'][0]['filename'] == name
    assert all(item['mode'] != 'v4' for item in result['reports'])
