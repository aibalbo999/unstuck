"""Protocol simulations check transport admission, never prove live HTTP."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
import time

import pytest

from data_fetch.market_sources import peer_reference_transport as t
from search_provider_runtime import SourceResponseError


def parts(request, *, body=b'<html>complete fixture</html>', status=200):
    return {'headers': (f'HTTP/2 {status}\r\nContent-Type: {request["mime"]}; charset={request["encoding"]}\r\n\r\n').encode(),
            'body': body, 'process_started': True,
            'metadata': json.dumps({'http_code': status, 'url_effective': request['url'],
                'ssl_verify_result': 0, 'proxy_used': 0, 'num_redirects': 0,
                'size_download': len(body)}).encode()}


def consume(request=None, value=None):
    request = request or t.spec('home')
    return t.PeerIncomeHttp()._consume(request, request['url'], value or parts(request), 0, None, {})


def own(packet, request, monkeypatch):
    import cache_store
    row = {'value': packet, 'fetched_at_epoch': packet['fetched_at_epoch'],
           'fresh_until_epoch': packet['fetched_at_epoch'] + t.TTL}
    key = 'shared_provider:v1:' + sha256(t.raw_key(request).encode()).hexdigest()
    monkeypatch.setattr(cache_store, 'peek_cache_json', lambda wanted: row if wanted == key else None)
    return row


def test_reference_nonce_has_one_stable_local_owner(monkeypatch):
    request = t.spec('reference', day=date(2026, 11, 4))
    url = request['url'] + '&_=1793814598691'
    value = parts(request, body=b'{"fixture":true}')
    metadata = json.loads(value['metadata']); metadata['url_effective'] = url
    value['metadata'] = json.dumps(metadata).encode()
    packet = t.PeerIncomeHttp()._consume(request, url, value, 0, None, {})
    own(packet, request, monkeypatch)
    assert t.receipt_body(packet, request) == value['body']
    assert t.raw_key(request) == t.raw_key(deepcopy(request))
    assert not t._url_matches(url + '&date=20260101', request)
    assert not t._url_matches(url.replace('1793814598691', 'guess'), request)


@pytest.mark.parametrize('change', ['status_bool', 'redirect', 'proxy', 'ssl', 'wrong_url',
    'partial', 'wrong_mime', 'wrong_charset', 'encoding', 'no_process', 'missing_metadata'])
def test_incomplete_or_unqualified_transport_does_not_create_a_receipt(change):
    request = t.spec('home'); value = parts(request); meta = json.loads(value['metadata'])
    if change == 'status_bool': meta['http_code'] = True
    elif change == 'redirect': meta['num_redirects'] = 1
    elif change == 'proxy': meta['proxy_used'] = 1
    elif change == 'ssl': meta['ssl_verify_result'] = 1
    elif change == 'wrong_url': meta['url_effective'] = 'https://example.invalid/'
    elif change == 'partial': meta['size_download'] += 1
    elif change == 'wrong_mime': value['headers'] = value['headers'].replace(b'text/html', b'application/json')
    elif change == 'wrong_charset': value['headers'] = value['headers'].replace(b'utf-8', b'big5')
    elif change == 'encoding': value['headers'] += b'Content-Encoding: gzip\r\n'
    elif change == 'no_process': value['process_started'] = False
    else: meta = {}
    value['metadata'] = json.dumps(meta).encode()
    with pytest.raises(SourceResponseError): consume(request, value)


def test_real_http_200_refusal_is_access_denied_not_fabricated_403(monkeypatch):
    failures = []
    monkeypatch.setattr(t, 'remember_failure', lambda key, exc: failures.append((key, exc)))
    body = ('<html><body>因為安全性考量，您所執行的頁面無法呈現。 '
        'FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED. '
        'OR CALL US FOR FURTHER HELP</body></html>').encode()
    with pytest.raises(SourceResponseError) as caught: consume(value=parts(t.spec('home'), body=body))
    assert caught.value.status_code == 200 and caught.value.diagnostic['http_status_observed'] is True
    assert caught.value.diagnostic['response_complete'] is False and failures


def test_429_keeps_retry_after_and_uses_existing_provider_cooldown(monkeypatch):
    calls = []
    import provider_throttle
    monkeypatch.setattr(provider_throttle, 'mark_rate_limit_cooldown', lambda provider, exc: calls.append((provider, exc)))
    monkeypatch.setattr(t, 'remember_failure', lambda *a: None)
    value = parts(t.spec('home'), status=429)
    value['headers'] += b'Retry-After: 120\r\n'
    with pytest.raises(SourceResponseError) as caught: consume(value=value)
    assert caught.value.status_code == 429 and caught.value.response.headers['retry-after'] == '120'
    assert calls[0][0] == 'TWSE MOPS official financial comparison'


@pytest.mark.parametrize('change', ['owner_missing', 'owner_expired', 'owner_renewed', 'raw_hash',
    'request_form', 'status_bool', 'manifest', 'old_epoch'])
def test_full_body_manifest_and_independent_original_owner_are_required(monkeypatch, change):
    request = t.spec('income', year=2026, quarter=2)
    packet = consume(request); owner = own(packet, request, monkeypatch)
    if change == 'owner_missing': monkeypatch.setattr('cache_store.peek_cache_json', lambda key: None)
    elif change == 'owner_expired': owner['fresh_until_epoch'] = time.time() - 1
    elif change == 'owner_renewed': owner['fresh_until_epoch'] = time.time() + t.TTL + 100
    elif change == 'raw_hash': packet['raw_receipt']['raw_response_sha256'] = 'f' * 64
    elif change == 'request_form': packet['spec']['data']['ys'] = '20252'
    elif change == 'status_bool': packet['native']['http_status'] = True
    elif change == 'manifest': packet['metadata_manifest'] = packet['raw_receipt']
    else: packet['fetched_at_epoch'] -= t.TTL + 1
    with pytest.raises((ValueError, OSError, EOFError)): t.receipt_body(packet, request)


def test_normal_warm_read_retains_original_bytes_epoch_and_deadline(monkeypatch):
    import shared_provider_cache
    import cache_store
    store = {}; writes = []; downloads = []
    def save(key, value, ttl_seconds=None):
        store[key] = deepcopy(value); writes.append(key)
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'peek_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'set_cache_json', save)
    def download(self, request, diagnostic):
        downloads.append(request)
        return self._consume(request, request['url'], parts(request), 0, None, diagnostic)
    monkeypatch.setattr(t.PeerIncomeHttp, '_download', download)
    request = t.spec('home')
    cold, first = t.PeerIncomeHttp().get(request); before = deepcopy(store)
    warm, second = t.PeerIncomeHttp().get(request)
    assert cold == warm and first == second and store == before
    assert len(downloads) == len(writes) == 1


def test_no_network_and_pre_request_timeout_have_no_inherited_http_status(monkeypatch):
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '1')
    request = t.spec('home'); diagnostic = {}
    with pytest.raises(SourceResponseError) as caught: t.PeerIncomeHttp()._download(request, diagnostic)
    assert caught.value.status_code is None and caught.value.diagnostic['http_status_observed'] is False
    assert diagnostic['http_request_sent'] is False
    client = t.PeerIncomeHttp(seconds=-1)
    with pytest.raises(SourceResponseError) as caught: client.get(request)
    assert caught.value.diagnostic['http_status_observed'] is False


def test_passive_children_keep_zero_record_count_and_exact_normal_source_identity(monkeypatch):
    import provider_correlation, provider_sla
    from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
    rows = []
    monkeypatch.setattr(provider_correlation, 'current_correlation', lambda:{
        'ticker':'3324.TWO','fetch_id':'fixture-fetch','operation_id':'fixture-operation'})
    monkeypatch.setattr(provider_correlation, 'current_source_identity', lambda:('dynamic_peer_metrics','FinMind/yfinance'))
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda values:rows.extend(values))
    with receipt_observation_scope(True): consume()
    assert len(rows) == 1 and rows[0]['record_count'] == 0
    assert rows[0]['event_kind'] == 'http_transport_receipt'
    assert rows[0]['selection_policy'] == 'transport-receipt-only:v1'
    rows.clear()
    with receipt_observation_scope(False): consume()
    assert not rows


def test_existing_raw_original_or_negative_guard_prevents_namespace_bypass(monkeypatch):
    import cache_store
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(t, 'proxy_url_for_request', lambda *a:None)
    monkeypatch.setattr(t, 'cooldown_state', lambda key:{})
    monkeypatch.setattr(t, 'collect_capped_process', lambda *a, **kw:pytest.fail('no request is allowed'))
    for field in ('fresh_until_epoch','retry_after_epoch'):
        monkeypatch.setattr(cache_store, 'peek_cache_json', lambda key:{field:time.time()+60})
        with pytest.raises(SourceResponseError) as caught: t.PeerIncomeHttp()._download(t.spec('home'),{})
        assert caught.value.error_kind == 'legacy_raw_cache_still_live'
        assert caught.value.diagnostic['http_status_observed'] is False


def test_exact_twse_methodology_uses_its_explicit_utf8_meta_when_header_omits_charset():
    request = t.spec('methodology')
    raw = b'<html><head><meta charset="utf-8"></head><body>fixture</body></html>'
    value = parts(request, body=raw)
    value['headers'] = b'HTTP/2 200\r\nContent-Type: text/html\r\n\r\n'
    packet = consume(request, value)
    assert t.receipt_body(packet, request, check_owner=False) == raw


@pytest.mark.parametrize('kind,meta,header', [
    ('home', '<meta charset="utf-8">', 'text/html'),
    ('methodology', '', 'text/html'),
    ('methodology', '<meta charset="big5">', 'text/html'),
    ('methodology', '<meta charset="utf-8"><meta charset="utf-8">', 'text/html'),
    ('methodology', '<meta charset="utf-8">', 'text/html; charset=big5'),
    ('methodology', '<meta charset="utf-8"><meta http-equiv="Content-Type" content="text/html; charset=big5">', 'text/html'),
])
def test_meta_rule_does_not_relax_other_routes_or_ambiguous_encoding(kind, meta, header):
    request = t.spec(kind)
    body = ('<html><head>'+meta+'</head><body>fixture</body></html>').encode()
    value = parts(request, body=body)
    value['headers'] = ('HTTP/2 200\r\nContent-Type: '+header+'\r\n\r\n').encode()
    with pytest.raises(SourceResponseError):consume(request, value)
