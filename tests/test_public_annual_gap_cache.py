"""Public boundary checks. Original private-data replay cases remain local."""
import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time
import pytest
FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/honprec2354_incomplete_public_annual_captured_20261011.json.gz'
PROVIDER = 'TWSE MOPS public annual JSON'

@pytest.fixture(autouse=True)
def isolated_cache_and_provider():
    import config, cache_store
    from cache_backends import InMemoryCache
    from provider_resilience import clear_provider_circuits
    from provider_throttle import clear_provider_throttles
    assert 'prompt-boundary-tests-' in str(config.CACHE_DB_PATH)
    cache_store.set_cache_backend(InMemoryCache())
    clear_provider_circuits(PROVIDER)
    clear_provider_throttles(PROVIDER)
    yield
    cache_store.reset_cache_store_for_tests()
    clear_provider_circuits(PROVIDER)
    clear_provider_throttles(PROVIDER)

class CapturedGapTransport:

    def __init__(self, *, break_missing_purchase_reconciliation=True):
        self.fixture = json.loads(gzip.decompress(FIXTURE.read_bytes()))
        if break_missing_purchase_reconciliation:
            for original in self.fixture['originals']:
                if not original['url'].endswith('/t164sb05'):
                    continue
                body = json.loads(base64.b64decode(original['body_b64']))
                rows = body['result']['reportList']
                labels = {row[0].strip() for row in rows if row and isinstance(row[0], str)}
                if '取得無形資產' in labels:
                    continue
                total = next((row for row in rows if row[0].strip() == '投資活動之淨現金流入（流出）'))
                for column in (1, 2):
                    amount = int(total[column].replace(',', '')) + 1
                    total[column] = ('-' if amount < 0 else '') + f'{abs(amount):,}'
                raw = json.dumps(body, ensure_ascii=False).encode()
                original.update(body_b64=base64.b64encode(raw).decode(), bytes=len(raw), sha256=sha256(raw).hexdigest())
        self.components = []
        self.calls = []
        self.position = 0
        self.deadline = time.monotonic() + 45
        self.batch_count = 0
        self.closed = False

    @contextmanager
    def batch(self):
        self.batch_count += 1
        self.position = 0
        try:
            yield self
        finally:
            self.closed = True

    def request(self, url, **kwargs):
        from official_response_evidence import archive_response
        expected = self.fixture['originals'][self.position]
        self.position += 1
        assert url == expected['url'] and kwargs == expected['request']
        raw = base64.b64decode(expected['body_b64'])
        assert len(raw) == expected['bytes'] and sha256(raw).hexdigest() == expected['sha256']
        self.calls.append((url, kwargs))
        self.components.append({'url': url, 'http_request_sent': True, 'http_status': 200, 'response_bytes': len(raw), 'response_sha256': expected['sha256'], 'status': 'complete'})
        return (raw, archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200))

def run(transport):
    from data_fetch.market_sources.mops_public_annual import fetch_public_financial_result
    return fetch_public_financial_result('2354.TW', transport=transport)

def test_confirmed_public_failure_warm_read_preserves_error_without_nineteen_downloads():
    from data_fetch.market_sources import mops_public_gap_cache as cache
    from provider_correlation import correlation_scope
    from provider_observation_details import observation_details
    from provider_acquisition import observation_kind
    cold_transport = CapturedGapTransport()
    warm_transport = CapturedGapTransport()
    with correlation_scope(replace=True, fetch_id='cold', ticker='2354.TW'):
        cold = run(cold_transport)
    with correlation_scope(replace=True, fetch_id='warm', ticker='2354.TW'):
        warm = run(warm_transport)
    assert cold['value'] is warm['value'] is None
    assert cold['audit']['message'] == cold_transport.fixture['expected_message']
    assert len(cold_transport.calls) == 19 and cold_transport.closed
    assert warm_transport.calls == [] and warm_transport.batch_count == 0
    a = warm['audit']
    assert a['status'] == 'error' and a['record_count'] == 0 and (a['error_kind'] == 'FilingError')
    assert a['cache_hit'] is True and a['stale'] is False and (a['event_kind'] == 'cache_hit')
    assert a['http_request_sent'] is False and a['http_request_count'] == 0
    assert a['component_statuses'] == {} and a['provider_attempts'] == [] and (a['provider_attempt_count'] == 0)
    assert a['fetch_id'] == 'warm' and a['fetched_at'] == cold['audit']['fetched_at']
    assert a['retry_at'] == datetime.fromisoformat(a['fetched_at']).timestamp() + cache.GAP_RETRY_SECONDS
    assert observation_kind({**a, 'details': observation_details(a)}) == 'empty_cache_count'
    assert observation_kind({**cold['audit'], 'details': observation_details(cold['audit'])}) == 'failed_count'

def test_exactly_reconciled_2354_originals_recover_missing_zero_facts_from_saved_official_evidence():
    from data_fetch.market_sources.mops_public_annual import project_public_history
    transport = CapturedGapTransport(break_missing_purchase_reconciliation=False)
    result = run(transport)
    assert result['audit']['status'] == 'success' and result['audit']['record_count'] == 5
    assert len(transport.calls) == 19 and transport.closed
    recovered = result['value']['inferred_zero_facts']
    assert recovered and {fact['period_year'] for fact in recovered} >= {2021, 2022, 2025}
    assert all((fact['proof'] == 'investment_cashflows_reconcile_to_reported_net_with_nonpositive_purchases' and fact['value_twd'] == 0 for fact in recovered))
    assert project_public_history(result['value'], '2354.TW') is not None

@pytest.mark.parametrize('damage', ['issuer', 'fingerprint', 'missing_original', 'body_hash', 'wrong_request', 'scope_in_body', 'success_status', 'positive_count', 'original_http', 'component_bytes', 'future_epoch', 'bool_epoch', 'timestamp_mismatch', 'old_body', 'expired'])
def test_unverified_or_expired_cached_gap_never_suppresses_real_acquisition(monkeypatch, damage):
    from data_fetch.market_sources import mops_public_gap_cache as source
    run(CapturedGapTransport())
    original_get = source.get_cache_json

    def altered(key):
        p = deepcopy(original_get(key))
        assert p is not None
        if damage == 'issuer':
            p['ticker'] = '3443.TW'
        elif damage == 'fingerprint':
            p['parser_fingerprint'] = '0' * 64
        elif damage == 'missing_original':
            p['originals'].pop()
        elif damage == 'body_hash':
            p['originals'][4]['raw_receipt']['raw_response_sha256'] = '0' * 64
        elif damage == 'wrong_request':
            p['originals'][4]['request']['json_body']['companyId'] = '3443'
        elif damage == 'scope_in_body':
            from official_response_evidence import read_response, archive_response
            receipt = p['originals'][4]['raw_receipt']
            value = json.loads(read_response(receipt))
            value['result']['reportType'] = '個體'
            raw = json.dumps(value, ensure_ascii=False).encode()
            new = archive_response(raw, source_url=receipt['source_url'], retrieved_at=receipt['retrieved_at'])
            p['originals'][4]['raw_receipt'] = new
            p['audit']['component_statuses']['4'].update(response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        elif damage == 'success_status':
            p['audit']['status'] = 'success'
        elif damage == 'positive_count':
            p['audit']['record_count'] = 1
        elif damage == 'original_http':
            p['originals'][0]['raw_receipt']['http_status'] = 429
        elif damage == 'component_bytes':
            p['audit']['component_statuses']['0']['response_bytes'] += 1
        elif damage == 'future_epoch':
            p['audit']['fetched_at_epoch'] = time.time() + 60
        elif damage == 'bool_epoch':
            p['audit']['fetched_at_epoch'] = True
        elif damage == 'timestamp_mismatch':
            p['audit']['fetched_at'] = '2026-01-01T00:00:00+00:00'
        elif damage == 'old_body':
            p['originals'][0]['raw_receipt']['retrieved_at'] -= 46
        elif damage == 'expired':
            stamp = time.time() - source.GAP_RETRY_SECONDS - 1
            p['audit'].update(fetched_at_epoch=stamp, fetched_at=datetime.fromtimestamp(stamp, timezone.utc).isoformat())
            for part in p['originals']:
                part['raw_receipt']['retrieved_at'] = stamp - 1
        return p
    monkeypatch.setattr(source, 'get_cache_json', altered)
    again = CapturedGapTransport()
    result = run(again)
    assert len(again.calls) == 19 and again.closed
    assert result['audit']['status'] == 'error' and result['audit']['cache_hit'] is False

def test_warm_reuse_never_extends_original_retry_time_or_inherits_data_fingerprint(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    from provider_correlation import correlation_scope
    writes = []
    setter = source.set_cache_json

    def recorded(*args):
        writes.append(args)
        return setter(*args)
    monkeypatch.setattr(source, 'set_cache_json', recorded)
    with correlation_scope(replace=True, fetch_id='first', data_fingerprint='a' * 64):
        first = run(CapturedGapTransport())
    assert len(writes) == 1 and writes[0][-1] == source.GAP_RETRY_SECONDS
    retry = datetime.fromisoformat(first['audit']['fetched_at']).timestamp() + source.GAP_RETRY_SECONDS
    for fetch_id in ['second', 'third']:
        transport = CapturedGapTransport()
        with correlation_scope(replace=True, fetch_id=fetch_id):
            warm = run(transport)
        assert not transport.calls and len(writes) == 1
        assert warm['audit']['retry_at'] == retry and warm['audit']['fetch_id'] == fetch_id
        assert 'data_fingerprint' not in warm['audit']

@pytest.mark.parametrize('failure', ['unverified_gap_string', 'transport', 'quota', 'unknown_local'])
def test_unverified_strings_transport_and_quota_are_not_issuer_gap_cache(monkeypatch, failure):
    from data_fetch.market_sources import mops_public_annual as native
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    from search_provider_runtime import SourceResponseError
    calls = []

    def fail(*args, **kwargs):
        calls.append('called')
        if failure == 'unverified_gap_string':
            raise FilingError('conflicting incomplete comparative statement for 2024')
        if failure == 'transport':
            raise SourceResponseError('transport_error')
        if failure == 'quota':
            raise SourceResponseError('rate_limited', status_code=429)
        raise TypeError('unknown native exception')
    monkeypatch.setattr(native, 'fetch_public_annual_histories', fail)
    for _ in range(2):
        result = run(CapturedGapTransport())
        assert result['value'] is None and result['audit']['status'] != 'success'
        assert result['audit']['cache_hit'] is False
    assert 1 <= len(calls) <= 2
    if failure != 'quota':
        assert len(calls) == 2

@pytest.mark.parametrize('failure', ['read', 'write'])
def test_optional_cache_failures_leave_original_acquisition_available(monkeypatch, failure):
    from data_fetch.market_sources import mops_public_gap_cache as source

    def broken(*args):
        raise OSError('synthetic cache failure')
    monkeypatch.setattr(source, 'get_cache_json' if failure == 'read' else 'set_cache_json', broken)
    for _ in range(2):
        transport = CapturedGapTransport()
        result = run(transport)
        assert len(transport.calls) == 19 and result['audit']['status'] == 'error'

def recovery_transport():
    recovered = CapturedGapTransport()
    for c in recovered.fixture['originals']:
        if not c['url'].endswith('/t164sb05'):
            continue
        value = json.loads(base64.b64decode(c['body_b64']))
        if not any((r[0].strip() == '取得無形資產' for r in value['result']['reportList'])):
            value['result']['reportList'].append(['取得無形資產', '0', '0'])
            rows = value['result']['reportList']
            total = next((r for r in rows if r[0].strip() == '投資活動之淨現金流入（流出）'))
            start = next((i for i, r in enumerate(rows) if r[0].strip() == '投資活動之現金流量'))
            end = next((i for i in range(start + 1, len(rows)) if rows[i][0].strip() == '投資活動之淨現金流入（流出）'))
            for col in (1, 2):
                total[col] = f"{sum((int(r[col].replace(',', '')) for r in rows[start + 1:end])):,}"
            raw = json.dumps(value, ensure_ascii=False).encode()
            c.update(body_b64=base64.b64encode(raw).decode(), bytes=len(raw), sha256=sha256(raw).hexdigest())
    return recovered

def test_expired_gap_can_recover_from_explicit_complete_facts_and_clears_gap(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    from data_fetch.market_sources.mops_public_annual import project_public_history
    run(CapturedGapTransport())
    getter = source.get_cache_json
    keys = []

    def expired(key):
        keys.append(key)
        p = deepcopy(getter(key))
        if p:
            stamp = time.time() - source.GAP_RETRY_SECONDS - 1
            p['audit'].update(fetched_at_epoch=stamp, fetched_at=datetime.fromtimestamp(stamp, timezone.utc).isoformat())
            for c in p['originals']:
                c['raw_receipt']['retrieved_at'] = stamp - 1
        return p
    monkeypatch.setattr(source, 'get_cache_json', expired)
    recovered = recovery_transport()
    result = run(recovered)
    assert len(recovered.calls) == 19 and result['audit']['status'] == 'success'
    assert project_public_history(result['value'], '2354.TW') is not None
    assert keys and getter(keys[-1]) is None

def test_recovery_after_cache_read_failure_clears_hidden_old_gap(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    run(CapturedGapTransport())
    getter = source.get_cache_json

    def unavailable(*args):
        raise OSError('transient read failure while old gap remains')
    monkeypatch.setattr(source, 'get_cache_json', unavailable)
    recovered = run(recovery_transport())
    assert recovered['audit']['status'] == 'success'
    monkeypatch.setattr(source, 'get_cache_json', getter)
    transport = recovery_transport()
    again = run(transport)
    assert again['audit']['status'] == 'success' and len(transport.calls) == 19

def test_malformed_cached_component_falls_through_to_original_fetch(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    run(CapturedGapTransport())
    getter = source.get_cache_json

    def malformed(key):
        p = deepcopy(getter(key))
        p['audit']['component_statuses']['0'] = []
        return p
    monkeypatch.setattr(source, 'get_cache_json', malformed)
    transport = CapturedGapTransport()
    result = run(transport)
    assert len(transport.calls) == 19 and result['audit']['cache_hit'] is False

def test_gap_expiring_during_full_readback_cannot_suppress_new_acquisition(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    cold = run(CapturedGapTransport())
    stamp = datetime.fromisoformat(cold['audit']['fetched_at']).timestamp()
    now = [stamp + 1]
    reader = source._receipt
    monkeypatch.setattr(source.time, 'time', lambda: now[0])

    def late(*args, **kwargs):
        now[0] = stamp + source.GAP_RETRY_SECONDS + 1
        return reader(*args, **kwargs)
    monkeypatch.setattr(source, '_receipt', late)
    transport = CapturedGapTransport()
    result = run(transport)
    assert result['audit']['cache_hit'] is False and len(transport.calls) == 19

def test_negative_readback_cannot_be_admitted_after_same_replay_deadline(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    run(CapturedGapTransport())
    base = source.time.monotonic()
    now = [base]
    reader = source._receipt
    transport = CapturedGapTransport()
    monkeypatch.setattr(source.time, 'monotonic', lambda: now[0])

    def late(*args, **kwargs):
        now[0] = base + 46
        return reader(*args, **kwargs)
    monkeypatch.setattr(source, '_receipt', late)
    result = run(transport)
    assert result['audit']['cache_hit'] is False

def test_saved_original_replay_timeout_falls_back_to_real_acquisition(monkeypatch):
    from data_fetch.market_sources import mops_public_gap_cache as source
    from search_provider_runtime import SourceResponseError
    run(CapturedGapTransport())

    def timed_out(*args, **kwargs):
        raise SourceResponseError('timeout')
    monkeypatch.setattr(source, 'fetch_public_annual_histories', timed_out)
    transport = CapturedGapTransport()
    result = run(transport)
    assert result['audit']['cache_hit'] is False and len(transport.calls) == 19
