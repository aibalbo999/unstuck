"""Saved native receipts through the real public snapshot-refresh boundary."""
import asyncio
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "tests")]
from report_persistence import report_bundle_keys_for_filename
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_refresh_acquisition_audit import init_db, events

K = ROOT / "docs/evidence/source-acquisition/20261016/remaining-content-recovery"
FIXTURES = K / "news-retention-implementation/fixtures"
PROVIDER = "TWSE company announcement history"
BUCKETS = ("recent_catalysts", "additional_recent_catalysts", "historical_catalysts",
           "unverified_catalysts", "identity_rejected_catalysts")


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def setup_saved(ticker):
    from runtime_paths import current_runtime_paths
    inventory = json.loads((K / "inventory.json").read_text())
    report = next(r for r in inventory["reports"] if r["ticker"] == ticker)
    old_path = FIXTURES / (ticker + ".old.json")
    old = json.loads(old_path.read_text())
    raw = (FIXTURES / (ticker + ".incoming.json")).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == report["data_sha256"]
    incoming = json.loads(raw)["data"]
    assert old["refreshed_from_report"] == report["filename"]
    originals = [r for k in BUCKETS for r in old["data"].get(k, [])
                 if r.get("source") == PROVIDER and r.get("text")]
    assert len(originals) == 1
    original = deepcopy(originals[0])
    assert hashlib.sha256(original["text"].encode()).hexdigest() == original["content_sha256"]
    audits = [a for a in old["source_audit"] if a.get("provider") == PROVIDER]
    assert len(audits) == 1 and audits[0]["status"] == "success"
    origin = deepcopy(audits[0])
    receipt = next(r["receipt"] for r in origin["source_record_archive"] if r.get("url") == original["link"])
    original_path = receipt["raw_response_path"]
    body_path = FIXTURES / "originals" / Path(original_path).name
    assert hashlib.sha256(gzip.decompress(body_path.read_bytes())).hexdigest() == receipt["raw_response_sha256"]
    destination = current_runtime_paths().cache_dir / "official-response-evidence"
    assert not destination.resolve().is_relative_to(ROOT / "backend/cache")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(body_path, destination / body_path.name)
    # Relocate only the captured original used in this test; do not fabricate
    # receipt fields, observation timestamps, body contents, or success audits.
    for item in walk(old):
        if item.get("raw_response_path") == original_path:
            item["raw_response_path"] = str(destination / body_path.name)
    return report["filename"], old, incoming, original, origin


def refresh(name, old, incoming, tmp_path):
    init_db()
    before_events = events()
    storage = InMemoryStorage()
    keys = report_bundle_keys_for_filename(name)
    for key, content, mime in ((keys.html_key, b"unchanged saved HTML", "text/html"),
                               (keys.md_key, b"unchanged saved Markdown", "text/markdown"),
                               (keys.data_key, json.dumps(old, ensure_ascii=False).encode(), "application/json")):
        storage.save_report(key, content, content_type=mime)
    provider_input = deepcopy(incoming)
    result = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=SimpleNamespace(), refreshed_data=incoming, return_refreshed_data=True))
    saved = json.loads(storage.get_report(keys.data_key).content)
    assert events() == before_events
    assert incoming == provider_input and result["refreshed_data"] == provider_input
    assert storage.get_report(keys.html_key).content == b"unchanged saved HTML"
    assert storage.get_report(keys.md_key).content == b"unchanged saved Markdown"
    incoming_failure = [a for a in incoming["source_audit"] if a.get("provider") == PROVIDER]
    saved_failure = [a for a in saved["data"]["source_audit"] if a.get("provider") == PROVIDER]
    assert saved_failure == incoming_failure
    assert incoming_failure[0]["record_count"] == 0
    return saved


@pytest.mark.parametrize("ticker", ["2367.TW", "3653.TW"])
def test_full_refresh_preserves_same_report_verified_body_after_cooldown(tmp_path, ticker):
    name, old, incoming, original, origin = setup_saved(ticker)
    assert not any(r.get("link") == original["link"] for k in BUCKETS for r in incoming.get(k, []))
    saved = refresh(name, old, incoming, tmp_path)
    retained = [r for k in ("recent_catalysts", "additional_recent_catalysts") for r in saved["data"].get(k, [])
                if r.get("link") == original["link"]]
    assert len(retained) == 1, "Full refresh dropped this report's previously verified complete native announcement"
    assert retained[0]["text"] == original["text"]
    assert retained[0]["content_sha256"] == original["content_sha256"]
    assert retained[0]["published_at"] == original["published_at"]
    marker = saved["data"]["news_retention"]
    assert marker["new_acquisition"] is False
    assert any(a["fetched_at_epoch"] == origin["fetched_at_epoch"] for a in marker["original_audits"])


@pytest.mark.parametrize("damage", ["missing_receipt", "altered_text", "different_issuer"])
def test_ineligible_saved_body_is_not_promoted(tmp_path, damage):
    name, old, incoming, original, _ = setup_saved("2367.TW")
    if damage == "missing_receipt":
        for item in walk(old):
            if item.get("provider") == PROVIDER:
                item["source_record_archive"] = []
    elif damage == "altered_text":
        for item in walk(old):
            if item.get("link") == original["link"] and item.get("text"):
                item["text"] += "Unverified changed text"
    else:
        incoming["company_identity"]["official_name"] = "另一家公司"
    saved = refresh(name, old, incoming, tmp_path)
    assert not any(r.get("link") == original["link"] for k in ("recent_catalysts", "additional_recent_catalysts")
                   for r in saved["data"].get(k, []))


def test_incoming_same_url_revision_is_not_replaced_by_old_body(tmp_path):
    name, old, incoming, original, _ = setup_saved("2367.TW")
    revised = deepcopy(original)
    revised["text"] += "\nThis is a changed incoming source payload."
    revised["content_sha256"] = hashlib.sha256(revised["text"].encode()).hexdigest()
    incoming["additional_recent_catalysts"].append(revised)
    saved = refresh(name, old, incoming, tmp_path)
    found = [r for k in BUCKETS for r in saved["data"].get(k, []) if r.get("link") == original["link"]]
    assert len(found) == 1 and found[0]["text"] == revised["text"]


def test_original_outside_thirty_days_is_never_promoted_to_recent(tmp_path, monkeypatch):
    name, old, incoming, original, _ = setup_saved("2367.TW")
    # The record and receipt remain untouched; only the real processing cutoff
    # advances. Historical preservation is permitted, recent evidence is not.
    from datetime import datetime, timezone
    cutoff = datetime(2026, 11, 2, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(time, "time", lambda: cutoff)
    saved = refresh(name, old, incoming, tmp_path)
    assert not any(r.get("link") == original["link"] for k in ("recent_catalysts", "additional_recent_catalysts")
                   for r in saved["data"].get(k, []))


def component(data):
    return next(a for a in data['source_audit'] if a.get('provider') == PROVIDER)


def assert_not_retained(saved, original):
    assert 'news_retention' not in saved['data']
    assert not any(r.get('link') == original['link'] for k in BUCKETS for r in saved['data'].get(k, []))


@pytest.mark.parametrize('damage', [
    'unknown_kind', 'no_observations', 'missing_observed_status', 'string_403', 'bool_status',
    'float_status', '403', '429', 'other_ticker', 'other_endpoint', 'bad_fingerprint',
    'index_other_ticker', 'future_epoch', 'bool_bytes',
])
def test_unqualified_current_failure_cannot_authorize_retention(tmp_path, damage):
    from data_fetch.market_sources.twse_announcement_progress import request_fingerprint
    name, old, incoming, original, _ = setup_saved('2367.TW')
    audit = component(incoming)
    failure = audit['request_observations'][-1]
    detail = audit['detail_observations'][-1]
    # Start from an explicit transport timeout, preserving the saved request
    # identity; individual cases then remove or contradict that qualification.
    audit['detail_stop_reason'] = failure['error_kind'] = detail['error_kind'] = 'timeout'
    failure['http_request_sent'] = True
    failure['http_request_count'] = detail['http_request_count'] = 1
    if damage == 'unknown_kind':
        audit['detail_stop_reason'] = failure['error_kind'] = detail['error_kind'] = 'unknown'
    elif damage == 'no_observations':
        audit['request_observations'] = []
    elif damage in ('missing_observed_status', 'string_403', 'bool_status', 'float_status', '403', '429'):
        failure['http_status_observed'] = True
        status = {'missing_observed_status': None, 'string_403': '403', 'bool_status': True,
                  'float_status': 200.0, '403': 403, '429': 429}[damage]
        failure['http_status'] = detail['http_status'] = status
    elif damage in ('other_ticker', 'other_endpoint'):
        url = (failure['url'].replace('COMPANY_ID=2367', 'COMPANY_ID=2368')
               if damage == 'other_ticker' else 'https://example.com/unrelated')
        failure['url'] = detail['url'] = url
        failure['request_fingerprint'] = detail['request_fingerprint'] = request_fingerprint('GET', url)
    elif damage == 'bad_fingerprint':
        failure['request_fingerprint'] = detail['request_fingerprint'] = '0' * 64
    elif damage == 'index_other_ticker':
        index = audit['request_observations'][0]
        index['request_fingerprint'] = request_fingerprint('GET', index['url'], params={'code': '2368'})
    elif damage == 'future_epoch':
        failure['response_retrieved_at_epoch'] = time.time() + 3600
    else:
        failure['response_bytes'] = False
    assert_not_retained(refresh(name, old, incoming, tmp_path), original)


@pytest.mark.parametrize('kind,status', [('timeout', None), ('transport_error', None), ('server_error', 503)])
def test_explicit_bound_transient_failure_preserves_verified_original(tmp_path, kind, status):
    name, old, incoming, original, _ = setup_saved('2367.TW')
    audit = component(incoming)
    failure, detail = audit['request_observations'][-1], audit['detail_observations'][-1]
    audit['detail_stop_reason'] = failure['error_kind'] = detail['error_kind'] = kind
    failure['http_status'] = detail['http_status'] = status
    failure['http_status_observed'] = status is not None
    failure['http_request_sent'] = True
    failure['http_request_count'] = detail['http_request_count'] = 1
    saved = refresh(name, old, incoming, tmp_path)
    assert saved['data']['news_retention']['records'][0]['link'] == original['link']


@pytest.mark.parametrize('damage', [
    'native_float_status', 'native_bool_bytes', 'native_float_bytes', 'native_bool_epoch',
    'native_future_epoch', 'missing_native', 'raw_tamper', 'parser_changed', 'receipt_hash',
    'receipt_float_status', 'receipt_bool_epoch', 'old_stock_id', 'incoming_stock_id', 'wrong_report',
])
def test_saved_original_requires_native_receipt_parser_and_same_report(tmp_path, damage):
    name, old, incoming, original, _ = setup_saved('2367.TW')
    audits = [component(old), component(old['data'])]
    for audit in audits:
        native = next(o for o in audit['request_observations'] if o['url'] == original['link'])
        proof = next(r['receipt'] for r in audit['source_record_archive'] if r['url'] == original['link'])
        if damage == 'native_float_status':
            native['http_status'] = 200.0
        elif damage == 'native_bool_bytes':
            native['response_bytes'] = True
        elif damage == 'native_float_bytes':
            native['response_bytes'] = float(native['response_bytes'])
        elif damage == 'native_bool_epoch':
            native['response_retrieved_at_epoch'] = True
        elif damage == 'native_future_epoch':
            native['response_retrieved_at_epoch'] = time.time() + 3600
        elif damage == 'missing_native':
            audit['request_observations'].remove(native)
        elif damage == 'raw_tamper':
            Path(proof['raw_response_path']).write_bytes(gzip.compress(b'changed original bytes'))
        elif damage == 'parser_changed':
            audit['parser_version'] = 'unverified-parser'
        elif damage == 'receipt_hash':
            proof['raw_response_sha256'] = '0' * 64
        elif damage == 'receipt_float_status':
            proof['http_status'] = 200.0
        elif damage == 'receipt_bool_epoch':
            proof['retrieved_at'] = True
    if damage == 'old_stock_id':
        old['data']['stock_id'] = '2368'
    elif damage == 'incoming_stock_id':
        incoming['stock_id'] = '2368'
    elif damage == 'wrong_report':
        old['refreshed_from_report'] = name.replace('015443', '015444')
    assert_not_retained(refresh(name, old, incoming, tmp_path), original)


def test_repeated_refresh_preserves_original_provenance_without_renewal(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    name, old, incoming, original, _ = setup_saved('2367.TW')
    now = time.time()
    monkeypatch.setattr(time, 'time', lambda: now)
    monkeypatch.setattr('report_refresh_service.utc_now_iso', lambda: datetime.fromtimestamp(now, timezone.utc).isoformat())
    first = refresh(name, old, incoming, tmp_path)
    second = refresh(name, first, incoming, tmp_path)
    third = refresh(name, second, incoming, tmp_path)
    for saved in (second, third):
        assert saved['data']['news_retention'] == first['data']['news_retention']
        assert saved['data']['source_freshness'] == first['data']['source_freshness']
        found = [r for k in BUCKETS for r in saved['data'].get(k, []) if r.get('link') == original['link']]
        assert len(found) == 1 and found[0]['published_at'] == original['published_at']


@pytest.mark.parametrize('damage', ['audit', 'binding', 'report'])
def test_broken_retention_chain_is_not_accepted(tmp_path, damage):
    name, old, incoming, original, _ = setup_saved('2367.TW')
    first = refresh(name, old, incoming, tmp_path)
    marker = first['data']['news_retention']
    if damage == 'audit':
        marker['original_audits'][0]['fetched_at_epoch'] += 1
    elif damage == 'binding':
        marker['records'][0]['content_sha256'] = '0' * 64
    else:
        marker['report_filename'] = 'another-report.html'
    assert_not_retained(refresh(name, first, incoming, tmp_path), original)


def test_shared_provider_payload_does_not_transfer_another_reports_original(tmp_path):
    name, old, shared, original, _ = setup_saved('2367.TW')
    saved = refresh(name, old, shared, tmp_path)
    assert 'news_retention' in saved['data']
    assert 'news_retention' not in shared
    second_name = name.replace('015443', '015444')
    second_old = deepcopy(old)
    second_old['refreshed_from_report'] = second_name
    second_old['data'] = deepcopy(shared)
    second_old['source_audit'] = deepcopy(shared['source_audit'])
    assert_not_retained(refresh(second_name, second_old, shared, tmp_path), original)


def revised_origin_snapshot(snapshot, original, *, version, different_url=False):
    """Generated native-response behavior fixture, never a formal acquisition."""
    from datetime import datetime, timezone
    from bs4 import BeautifulSoup, NavigableString
    from official_response_evidence import archive_response
    from data_fetch.market_sources.twse_announcement_progress import request_fingerprint
    import report_news_retention as subject
    acquired = deepcopy(snapshot)
    audit = deepcopy(snapshot['data']['news_retention']['original_audits'][0])
    entry = next(e for e in audit['source_record_archive'] if e.get('url') == original['link'])
    native = next(o for o in audit['request_observations'] if o.get('url') == original['link'])
    raw = gzip.decompress(Path(entry['receipt']['raw_response_path']).read_bytes())
    soup = BeautifulSoup(raw.decode(), 'html.parser')
    body_label = next(t for t in soup.select('th') if subject._text(t.get_text()) == '說明')
    body_label.find_next_sibling('td').append(NavigableString(f'\n隔離測試正文修訂 {version}，不是正式來源原文。'))
    revised = deepcopy(original)
    if different_url:
        title = next(t for t in soup.select('th') if subject._text(t.get_text()) == '主旨')
        title.find_next_sibling('td').append(NavigableString('第二份隔離測試公告'))
        revised['link'] = original['link'].replace('SEQ_NO=1', 'SEQ_NO=2')
    url = revised['link']
    raw = str(soup).encode()
    epoch = time.time()
    proof = archive_response(raw, source_url=url, retrieved_at=epoch, max_bytes=subject.MAX_BYTES)
    fingerprint = request_fingerprint('GET', url)
    entry.update(url=url, request_fingerprint=fingerprint, receipt=proof)
    native.update(url=url, request_fingerprint=fingerprint, response_sha256=proof['raw_response_sha256'],
                  response_bytes=len(raw), response_retrieved_at_epoch=epoch)
    audit.update(fetch_id=f'isolated-source-version-{version}', fetched_at_epoch=epoch, body_fetched_at_epoch=epoch)
    _, fields = subject._detail_fields(raw.decode())
    revised['title'] = subject._text(fields['主旨'])
    revised['text'] = f"燿華（2367） {revised['title']}\n{fields['說明'].strip()}"
    revised['summary'] = revised['text'][:1500]
    revised['content_sha256'] = hashlib.sha256(revised['text'].encode()).hexdigest()
    subject._replay(revised, audit, '2367.TW', '燿華', time.monotonic() + 2)
    for key in BUCKETS:
        acquired['data'][key] = [r for r in acquired['data'].get(key, []) if r.get('link') != revised['link']]
    acquired['data']['additional_recent_catalysts'].append(revised)
    audits = [a for a in acquired['data']['source_audit'] if a.get('provider') != PROVIDER] + [audit]
    acquired['source_audit'] = deepcopy(audits)
    acquired['data']['source_audit'] = deepcopy(audits)
    acquired['snapshot_refreshed_at'] = datetime.now(timezone.utc).isoformat()
    return acquired, revised, audit


def test_successive_same_url_native_versions_do_not_grow_retention_origins(tmp_path):
    name, old, incoming, original, _ = setup_saved('2367.TW')
    saved = refresh(name, old, incoming, tmp_path)
    for version in (1, 2, 3):
        acquired, revised, audit = revised_origin_snapshot(saved, original, version=version)
        saved = refresh(name, acquired, incoming, tmp_path)
        marker = saved['data']['news_retention']
        assert len(marker['original_audits']) == len(marker['original_snapshot_at_epochs']) == 1
        assert marker['original_audits'][0] == audit
        assert marker['records'][0]['original_fetched_at_epoch'] == audit['fetched_at_epoch']
        assert marker['records'][0]['content_sha256'] == revised['content_sha256']
        original = revised


def test_new_distinct_original_keeps_prior_original_and_each_native_epoch(tmp_path):
    name, old, incoming, original, _ = setup_saved('2367.TW')
    first = refresh(name, old, incoming, tmp_path)
    previous_marker = deepcopy(first['data']['news_retention'])
    acquired, revised, audit = revised_origin_snapshot(first, original, version=1, different_url=True)
    saved = refresh(name, acquired, incoming, tmp_path)
    marker = saved['data']['news_retention']
    assert len(marker['original_audits']) == 2
    assert marker['original_audits'][0] == previous_marker['original_audits'][0]
    assert marker['original_snapshot_at_epochs'][0] == previous_marker['original_snapshot_at_epochs'][0]
    assert marker['original_audits'][1] == audit
    assert {b['link'] for b in marker['records']} == {original['link'], revised['link']}
    assert refresh(name, saved, incoming, tmp_path)['data']['news_retention'] == marker


@pytest.mark.parametrize('damage', ['new_body_contradiction', 'old_marker_tamper'])
def test_new_origin_cannot_hide_a_changed_body_or_bypass_old_marker_verification(tmp_path, damage):
    name, old, incoming, original, _ = setup_saved('2367.TW')
    first = refresh(name, old, incoming, tmp_path)
    acquired, revised, _ = revised_origin_snapshot(first, original, version=1)
    if damage == 'new_body_contradiction':
        # A newer audit proves revised bytes, while the saved body claims the
        # older version. Do not choose the old receipt just because it matches.
        for key in BUCKETS:
            acquired['data'][key] = [deepcopy(original) if r.get('link') == original['link'] else r
                                     for r in acquired['data'].get(key, [])]
    else:
        acquired['data']['news_retention']['records'][0]['raw_response_sha256'] = '0' * 64
    assert_not_retained(refresh(name, acquired, incoming, tmp_path), original)
