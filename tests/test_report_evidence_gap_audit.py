"""Evidence-gap inventory cannot mutate originals or hide the newest bad snapshot."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_report_evidence_gaps import audit
from test_report_data_gap_audit import reports


def test_evidence_inventory_preserves_artifacts_and_database(tmp_path):
    storage, db = reports(tmp_path)
    for item in storage.list_reports():
        if item.key.endswith('.data.json'):
            value = json.loads(item.content if hasattr(item, 'content') else storage.get_report(item.key).content)
            value['data'] = {'ticker': '2330.TW'}
            storage.save_report(item.key, json.dumps(value).encode(), content_type='application/json')
    before = {item.key: storage.get_report(item.key).content for item in storage.list_reports()}
    db_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    result = audit(db, storage._root)
    assert result['reports_checked'] == 2 and not result['errors']
    assert all(storage.get_report(key).content == raw for key, raw in before.items())
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_hash


def test_bad_latest_snapshot_is_not_replaced_with_a_successful_old_one(tmp_path):
    storage, db = reports(tmp_path)
    result = audit(db, storage._root)
    assert result['reports_checked'] == 0
    assert len(result['errors']) == 2
