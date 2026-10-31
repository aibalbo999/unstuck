"""Public master acquisition regression; captured complete originals, no HTTP."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]
from test_shared_provider_cache import memory_cache
from test_official_issuer_master_json import json_value, RAW


@pytest.fixture
def public_master(monkeypatch, memory_cache):
    from data_fetch.market_sources import official_issuer_master as master
    from data_fetch.market_sources.official_issuer_master_transport import IssuerMasterHttp
    from search_provider_runtime import SourceResponseError
    clock = [1791948208.]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    calls = []
    controls = {'csv': 'timeout', 'json_policy': 'max-age=300'}
    csv = (ROOT / 'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes()
    def download(self, url, diagnostic):
        assert url in (master.MASTER_URL, master.JSON_URL)
        calls.append(url)
        self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=200)
        if url == master.JSON_URL:
            return json_value(policy=controls['json_policy'])
        if controls['csv'] == 'timeout':
            raise SourceResponseError('timeout', status_code=200)
        assert controls['csv'] == 'no-store-success'
        metadata = {'http_status':200, 'effective_url':url, 'num_redirects':0,
            'size_download':len(csv), 'content_type':'text/csv', 'content_length':len(csv),
            'method':'GET', 'proxy_used':0, 'cache_control':'no-store'}
        metadata = master.master_metadata(metadata, csv, {})
        diagnostic['response_metadata'] = metadata
        return {'url':url, 'body_b64':base64.b64encode(csv).decode(), 'sha256':sha256(csv).hexdigest(),
                'request_method':'GET', 'request_body':None, 'response_metadata':metadata}
    monkeypatch.setattr(IssuerMasterHttp, 'download_original', download)
    return master, IssuerMasterHttp, calls, controls, clock


@pytest.mark.parametrize('csv_after_cooldown', ['timeout', 'no-store-success'])
def test_valid_warm_json_avoids_a_new_csv_get_after_csv_lease_expires(public_master, csv_after_cooldown):
    import cache_store
    m, Http, calls, control, clock = public_master
    first_http = Http(time.monotonic()+25.)
    raw, original = first_http.get_receipt(m.MASTER_URL)
    assert raw == RAW and original['source_url'] == m.JSON_URL
    assert original['cache_hit'] is False and original['reusable'] is True
    assert calls == [m.MASTER_URL, m.JSON_URL]
    assert cache_store.get_cache_json(m.CACHE_KEY) is None
    saved_json = deepcopy(cache_store.get_cache_json(m._parameters(m.JSON_URL)[2]))
    stamp = original['retrieved_at']
    assert original['fresh_until_epoch'] == stamp+300.
    # Existing CSV failure reservation is 120 s. JSON remains fully valid.
    clock[0] = stamp+121.
    control['csv'] = csv_after_cooldown
    calls.clear()
    second_http = Http(time.monotonic()+25., force_refresh=True, use_cache=False)
    second, warm = second_http.get_receipt(m.MASTER_URL)
    assert calls == [], 'Valid complete warm JSON must not wait for or replace itself with a new CSV request'
    assert second_http.http_request_count == 0
    assert second == RAW and warm['source_url'] == m.JSON_URL and warm['cache_hit'] is True
    assert warm['retrieved_at'] == stamp and warm['fresh_until_epoch'] == stamp+300.
    assert warm['wire_original'] == original['wire_original']
    assert cache_store.get_cache_json(m._parameters(m.JSON_URL)[2]) == saved_json
    assert all(part.get('http_request_sent') is False for part in second_http.components)


@pytest.mark.parametrize('csv_mode', ['timeout', 'no-store-success'])
def test_absent_json_never_authorizes_a_speculative_json_request(public_master, csv_mode):
    m, Http, calls, control, _ = public_master
    control['csv'] = csv_mode
    _, receipt = Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    assert calls == ([m.MASTER_URL, m.JSON_URL] if csv_mode == 'timeout' else [m.MASTER_URL])
    assert receipt['cache_hit'] is False


def test_expired_json_reenters_normal_csv_then_json_acquisition(public_master):
    m, Http, calls, _, clock = public_master
    _, original = Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    clock[0] = original['fresh_until_epoch'] + 1.
    calls.clear()
    _, next_receipt = Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    assert calls == [m.MASTER_URL, m.JSON_URL]
    assert next_receipt['cache_hit'] is False and next_receipt['retrieved_at'] == clock[0]
    assert original['retrieved_at'] < next_receipt['retrieved_at']


def test_invalid_json_is_not_a_reusable_identity_or_refetch_permission(public_master):
    import cache_store
    from search_provider_runtime import SourceResponseError
    m, Http, calls, _, clock = public_master
    _, original = Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    key = m._parameters(m.JSON_URL)[2]
    row = deepcopy(cache_store.get_cache_json(key))
    row['receipt']['raw_response_sha256'] = '0'*64
    cache_store.set_cache_json(key, row, ttl_seconds=300)
    clock[0] = original['retrieved_at'] + 10.
    calls.clear()
    with pytest.raises(SourceResponseError) as error:
        Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    assert error.value.error_kind == 'cache_receipt_invalid'
    assert not calls and cache_store.get_cache_json(key) == row


@pytest.mark.parametrize('status,kind', [(403,'access_denied'), (429,'rate_limited')])
def test_known_terminal_csv_guard_is_not_hidden_by_warm_json(public_master, status, kind):
    import cache_store
    from search_provider_runtime import SourceResponseError
    m, Http, calls, _, clock = public_master
    _, original = Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    clock[0] = original['retrieved_at']+10.
    guard = {'token':'terminal-test', 'retry_at':clock[0]+120., 'http_status':status,
             'error_kind':kind, 'fallback_eligible':False}
    cache_store.set_cache_json(m.ADMISSION_KEY, guard, ttl_seconds=120)
    calls.clear()
    with pytest.raises(SourceResponseError) as error:
        Http(time.monotonic()+25., force_refresh=True, use_cache=False).get_receipt(m.MASTER_URL)
    assert error.value.error_kind == kind
    assert not calls and cache_store.get_cache_json(m.ADMISSION_KEY) == guard


def test_busy_admission_cannot_become_a_hidden_native_request(public_master, monkeypatch):
    from contextlib import contextmanager
    from search_provider_runtime import SourceResponseError
    m, Http, calls, _, _ = public_master
    Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    @contextmanager
    def busy(*args, **kwargs):
        yield False
    monkeypatch.setattr(m, '_shared_lock', busy)
    calls.clear()
    with pytest.raises(SourceResponseError) as error:
        Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    assert error.value.error_kind == 'single_flight_busy' and not calls


def test_expired_total_deadline_cannot_deliver_even_a_warm_json(public_master):
    from search_provider_runtime import SourceResponseError
    m, Http, calls, _, _ = public_master
    Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    calls.clear()
    with pytest.raises(SourceResponseError) as error:
        Http(time.monotonic()-1.).get_receipt(m.MASTER_URL)
    assert error.value.error_kind == 'timeout' and not calls


@pytest.mark.parametrize('issuer', [
    'chb', 'chroma', 'eikei', 'fubon', 'getac', 'innocare', 'lienhwa', 'macronix',
    'nanyapcb', 'npc', 'sinbon', 'tecom', 'voltronic', 'wahlee', 'walsin', 'zdt',
])
def test_delegated_issuer_transport_reuses_warm_json_without_inheritance(public_master, monkeypatch, issuer):
    from importlib import import_module
    m, Http, calls, _, clock = public_master
    _, original = Http(time.monotonic()+25.).get_receipt(m.MASTER_URL)
    clock[0] = original['retrieved_at']+121.
    transport = import_module(f'data_fetch.market_sources.{issuer}_conference_transport')
    def no_download(*args, **kwargs):
        pytest.fail('A delegated master call must reuse the valid JSON original')
    monkeypatch.setattr(transport.ConferenceHttp, 'download_original', no_download)
    calls.clear()
    http = transport.ConferenceHttp(time.monotonic()+25.)
    raw, warm = http.get_receipt(m.MASTER_URL)
    assert raw == RAW and warm['cache_hit'] is True
    assert warm['retrieved_at'] == original['retrieved_at']
    assert warm['fresh_until_epoch'] == original['fresh_until_epoch']
    assert not calls and http.http_request_count == 0
