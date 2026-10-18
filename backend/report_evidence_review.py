"""Checksum-bound supplemental originals, separate from original report data."""
import hashlib
import json

from report_artifacts import ReportArtifactLocator

SCHEMA = 'report-evidence-review:v1'


def review_key(data_key):
    if not data_key.endswith('.data.json'):
        raise ValueError('Invalid report data artifact key')
    return data_key[:-len('.data.json')] + '.evidence-review.json'


def load_review(storage, filename, data_content):
    key = ReportArtifactLocator(storage).require_key(filename, kind='data')
    item = storage.get_report(review_key(key))
    if item is None:
        return {}, None
    value = json.loads(item.content)
    if (not isinstance(value, dict) or value.get('schema') != SCHEMA
            or value.get('filename') != filename
            or not isinstance(value.get('institutional_reports'), list)
            or len(value['institutional_reports']) > 60):
        raise ValueError('Invalid supplemental evidence review')
    if value.get('data_file_sha256') != hashlib.sha256(data_content).hexdigest():
        return {}, None
    return value, {'key': review_key(key), 'sha256': hashlib.sha256(item.content).hexdigest()}
