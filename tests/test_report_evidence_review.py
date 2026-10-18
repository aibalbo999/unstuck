import hashlib
import json

import pytest

from report_evidence_review import SCHEMA, load_review, review_key
from test_report_reader_migration import fixture_bundle


def test_review_is_checksum_bound_and_cannot_apply_to_a_different_snapshot(tmp_path):
    storage, db, name, html_key, _ = fixture_bundle(tmp_path)
    key = html_key.replace('.html', '.data.json')
    raw = storage.get_report(key).content
    value = {'schema': SCHEMA, 'filename': name, 'data_file_sha256': hashlib.sha256(raw).hexdigest(),
             'institutional_reports': [], 'historical_pit_verified': False}
    storage.save_report(review_key(key), json.dumps(value).encode(), content_type='application/json')
    assert load_review(storage, name, raw)[0] == value
    assert load_review(storage, name, raw+b' ')[0] == {}
    value['filename'] = 'other.html'
    storage.save_report(review_key(key), json.dumps(value).encode(), content_type='application/json')
    with pytest.raises(ValueError, match='supplemental'):
        load_review(storage, name, raw)


def test_migration_refuses_a_review_changed_after_its_snapshot_read(tmp_path, monkeypatch):
    import report_reader_migration as migration
    storage, db, name, html_key, _ = fixture_bundle(tmp_path)
    key = html_key.replace('.html', '.data.json')
    raw = storage.get_report(key).content
    value = {'schema': SCHEMA, 'filename': name, 'data_file_sha256': hashlib.sha256(raw).hexdigest(),
             'institutional_reports': []}
    storage.save_report(review_key(key), json.dumps(value).encode(), content_type='application/json')
    load = migration._reader_snapshot
    def changed(*args):
        result = load(*args)
        storage.save_report(review_key(key), b'changed', content_type='application/json')
        return result
    monkeypatch.setattr(migration, '_reader_snapshot', changed)
    with pytest.raises(ValueError, match='review changed'):
        migration.migrate_report(db, storage, name, apply=True)
