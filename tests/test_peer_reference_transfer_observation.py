"""Native curl observations are finite diagnostics, never HTTP/data success."""
from copy import deepcopy
import json
import pytest

from data_fetch.market_sources import peer_reference_transport as transport
from data_fetch.market_sources.starair_reference_spec import spec
from official_master_transport_observation import sanitize_observation
from provider_observation_details import observation_details
from provider_correlation import correlation_scope, source_operation
from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
from provider_acquisition import observation_kind
from search_provider_runtime import SourceResponseError
from test_peer_reference_transport import parts


def native_attempt(monkeypatch, *, metadata=None, process=True, status=0, rc=28):
    import provider_sla
    entries = []
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda rows: entries.extend(rows))
    request = spec('income', year=2025, quarter=2)
    value = parts(request, body=b'', status=status)
    value.update(headers=b'', process_started=process)
    value['metadata'] = json.dumps(metadata or {}).encode()
    with correlation_scope(replace=True, ticker='6757.TW', fetch_id='f'), source_operation('dynamic_peer_metrics', 'FinMind/yfinance'), receipt_observation_scope(True):
        with pytest.raises(SourceResponseError):
            transport.PeerIncomeHttp(peer_ticker='2646.TW')._consume(request, request['url'], value, rc, 'timeout', {'url': request['url']})
    return entries


def test_timeout_preserves_finite_curl_values_without_fabricating_HTTP_or_phase(monkeypatch):
    metadata = {'time_namelookup': .012, 'time_connect': .02, 'time_appconnect': 0,
        'time_starttransfer': 0, 'time_total': 2.001, 'http_version': '0',
        'headers': 'Authorization: secret', 'url_effective': 'https://secret.invalid/?token=secret'}
    entry, = native_attempt(monkeypatch, metadata=metadata)
    observed = observation_details(entry)
    expected = sanitize_observation({**metadata, 'process_exit_code': 28, 'response_bytes': 0})
    assert observed['component_statuses'][0]['transfer_observation'] == expected
    assert observed['http_status_observed'] is False and 'http_status' not in observed
    assert entry['http_status'] is None and entry['http_request_sent'] is None
    assert observed['component_statuses'][0]['error_kind'] == 'timeout'
    assert 'secret' not in json.dumps(observed) and 'Authorization' not in json.dumps(observed)
    assert entry['record_count'] == 0
    assert observation_kind({**entry, 'details': observed}) == 'aggregate_count'


@pytest.mark.parametrize('value', [True, '1.2', -1, float('nan'), float('inf'), 3601, 10**1000])
def test_invalid_or_unbounded_timing_is_omitted(monkeypatch, value):
    entry, = native_attempt(monkeypatch, metadata={'time_total': value})
    actual = observation_details(entry)['component_statuses'][0]['transfer_observation']
    assert actual == {'process_exit_code': 28, 'response_bytes': 0}


def test_missing_metadata_does_not_create_zero_DNS_TCP_TLS_TTFB_values(monkeypatch):
    entry, = native_attempt(monkeypatch)
    actual = observation_details(entry)['component_statuses'][0]['transfer_observation']
    assert actual == {'process_exit_code': 28, 'response_bytes': 0}


def test_process_not_started_cannot_create_native_transfer_observation(monkeypatch):
    assert native_attempt(monkeypatch, metadata={'time_total': .2}, process=False) == []


@pytest.mark.parametrize('change', ['provider', 'source', 'event', 'record_count', 'url', 'method', 'cache'])
def test_other_sources_requests_and_cache_cannot_inherit_income_POST_observation(monkeypatch, change):
    entry, = native_attempt(monkeypatch, metadata={'time_total': 2})
    entry = deepcopy(entry)
    if change == 'provider': entry['provider'] = 'unrelated'
    elif change == 'source': entry['source'] = 'financial_statements'
    elif change == 'event': entry['event_kind'] = 'aggregate'
    elif change == 'record_count': entry['record_count'] = 1
    elif change == 'url': entry['component_statuses'][0]['url'] += '?credential=secret'
    elif change == 'method': entry['component_statuses'][0]['request_method'] = 'GET'
    else: entry['component_statuses'][0]['cache_hit'] = True
    assert 'transfer_observation' not in observation_details(entry)['component_statuses'][0]


def test_old_saved_event_without_observation_remains_unknown(monkeypatch):
    entry, = native_attempt(monkeypatch)
    entry['component_statuses'][0].pop('transfer_observation', None)
    assert 'transfer_observation' not in observation_details(entry)['component_statuses'][0]


@pytest.mark.parametrize('status', [200, 429, 504])
def test_actual_HTTP_status_receipt_and_retry_after_are_unchanged(monkeypatch, status):
    import provider_sla, provider_throttle
    entries = []
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda rows: entries.extend(rows))
    monkeypatch.setattr(provider_throttle, 'mark_rate_limit_cooldown', lambda *args: None)
    monkeypatch.setattr(transport, 'remember_failure', lambda *args: None)
    request = spec('income', year=2025, quarter=2)
    value = parts(request, status=status)
    value['headers'] += b'Retry-After: 120\r\n'
    metadata = json.loads(value['metadata'])
    metadata.update(time_total=.5, time_starttransfer=.4, http_version='2')
    value['metadata'] = json.dumps(metadata).encode()
    with correlation_scope(replace=True, ticker='6757.TW', fetch_id='f'), source_operation('dynamic_peer_metrics', 'FinMind/yfinance'), receipt_observation_scope(True):
        http = transport.PeerIncomeHttp(peer_ticker='2646.TW')
        if status == 200:
            packet = http._consume(request, request['url'], value, 0, None, {'url': request['url']})
            assert 'transfer_observation' not in packet
            assert packet['native']['http_status'] == 200
        else:
            with pytest.raises(SourceResponseError) as error:
                http._consume(request, request['url'], value, 0, None, {'url': request['url']})
            assert error.value.status_code == status
            assert error.value.response.headers['retry-after'] == '120'
    entry, = entries
    projected = observation_details(entry)
    assert projected['http_status'] == status and projected['http_status_observed'] is True
    assert projected['component_statuses'][0]['transfer_observation']['time_total'] == .5
    assert entry['record_count'] == 0


def test_stale_diagnostic_is_removed_when_no_native_process_started():
    request = spec('income', year=2025, quarter=2)
    value = parts(request, status=0, body=b'')
    value.update(headers=b'', metadata=b'{}', process_started=False)
    diagnostic = {'url': request['url'], 'transfer_observation': {'time_total': 999}}
    with pytest.raises(SourceResponseError):
        transport.PeerIncomeHttp(peer_ticker='2646.TW')._consume(request, request['url'], value, 28, 'timeout', diagnostic)
    assert 'transfer_observation' not in diagnostic


def test_warm_income_original_does_not_emit_or_renew_transfer_observations(monkeypatch):
    import cache_store, provider_sla
    store, entries, downloads = {}, [], []
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'peek_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds=None: store.update({key: deepcopy(value)}))
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda rows: entries.extend(rows))
    def download(self, request, diagnostic):
        downloads.append(request)
        value = parts(request)
        meta = json.loads(value['metadata']); meta['time_total'] = .5
        value['metadata'] = json.dumps(meta).encode()
        return self._consume(request, request['url'], value, 0, None, diagnostic)
    monkeypatch.setattr(transport.PeerIncomeHttp, '_download', download)
    request = spec('income', year=2025, quarter=2)
    with correlation_scope(replace=True, ticker='6757.TW', fetch_id='f'), source_operation('dynamic_peer_metrics', 'FinMind/yfinance'), receipt_observation_scope(True):
        cold = transport.PeerIncomeHttp(peer_ticker='2646.TW').get(request)
        before = deepcopy(store)
        warm_http = transport.PeerIncomeHttp(peer_ticker='2646.TW')
        warm = warm_http.get(request)
    assert cold == warm and store == before and len(downloads) == len(entries) == 1
    assert 'transfer_observation' not in warm_http.components[0]
    assert 'transfer_observation' not in warm[1]
