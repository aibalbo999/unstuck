"""Long public annual queries retain hashes without widening generic URLs."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

import pytest


def captured_entry():
    from curl_cffi.requests import Response, Headers
    from curl_cffi.requests.models import Request
    from provider_correlation import correlation_scope, source_operation, current_correlation
    from yahoo_annual_original import capture_peer_annual_response
    from yfinance.const import fundamentals_keys
    types = ','.join('annual' + k for k in fundamentals_keys['balance-sheet'])
    public_url = ('https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/'
                  '3017.TW?symbol=3017.TW&type=' + quote(types, safe=','))
    url = public_url + '&crumb=private-test-value'
    response = Response(request=Request(url, Headers({'Cookie': 'private-test-value'}), 'GET'))
    response.url = url
    response.content = gzip.decompress((Path(__file__).parent /
        'fixtures/source_acquisition/peer_annual_balance_3017_20261103.json.gz').read_bytes())
    with correlation_scope(replace=True, ticker='2354.TW', fetch_id='isolated-long-annual'):
        with source_operation('dynamic_peer_metrics', 'FinMind/yfinance'):
            owner = current_correlation()
            proof = capture_peer_annual_response(response, binding=owner, symbol='3017.TW')
    assert proof and proof['source_url'] == public_url and len(public_url) == 4325
    return {**owner, 'source': 'dynamic_peer_metrics', 'provider': 'yfinance peer annual statements native HTTP',
            'status': 'success', 'record_count': 0, 'event_kind': 'http_transport_receipt',
            'selection_policy': 'transport-receipt-only:v1',
            'http_request_sent': True, 'raw_http_receipt': proof}, public_url


def test_actual_full_balance_body_keeps_original_hash_in_canonical_details():
    import provider_sla
    from provider_acquisition import get_provider_acquisition_summary
    from provider_observation_details import observation_details
    entry, url = captured_entry()
    details = observation_details(entry)
    receipt = details['original_http_receipts'][0]
    assert receipt['source_url_sha256'] == sha256(url.encode()).hexdigest()
    assert receipt['response_sha256'] == 'd7affcd7b41a90a915493e2a9f4cfd99fac6964fe51b1351c1284c2df61ee8a2'
    assert receipt['response_bytes'] == 49619 and receipt['response_complete'] is True
    assert receipt['original_cache_hit'] is False and receipt['http_request_sent'] is True
    provider_sla.record_source_audit_entries([entry])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        encoded = db.execute('select details_json from provider_sla_events order by id desc limit 1').fetchone()[0]
    assert json.loads(encoded)['original_http_receipts'] == details['original_http_receipts']
    assert not any(s in encoded for s in ['https://', 'annualTotalAssets', 'private-test-value', 'crumb', 'raw_response_path'])
    source = get_provider_acquisition_summary()['sources'][0]
    assert source['fetch_attempts'] == source['fetched_count'] == 0


@pytest.mark.parametrize('change', ['other_host', 'other_path', 'quarterly', 'unknown_series', 'duplicate_series',
                                  'credentials', 'query_secret', 'fragment', 'port', 'oversize', 'false_marker',
                                  'missing_marker', 'raw_kind', 'no_method'])
def test_long_exception_is_only_canonical_public_annual_metadata(change):
    from provider_observation_details import observation_details
    entry, url = captured_entry()
    proof = entry['raw_http_receipt']
    if change == 'other_host': url = url.replace('query2.finance.yahoo.com', 'example.com')
    elif change == 'other_path': url = url.replace('/ws/fundamentals-timeseries/', '/other/')
    elif change == 'quarterly': url = url.replace('annual', 'quarterly')
    elif change == 'unknown_series': url += ',annualFake'
    elif change == 'duplicate_series': url += ',annualTotalAssets'
    elif change == 'credentials': url = url.replace('https://', 'https://user:secret@')
    elif change == 'query_secret': url += '&crumb=private-test-value'
    elif change == 'fragment': url += '#private'
    elif change == 'port': url = url.replace('query2.finance.yahoo.com', 'query2.finance.yahoo.com:443')
    elif change == 'oversize': url += ',annualTotalAssets' * 1000
    elif change == 'false_marker': proof['financial_semantics_verified'] = 0
    elif change == 'missing_marker': proof.pop('financial_semantics_verified')
    elif change == 'raw_kind': proof['evidence_kind'] = 'raw_http_response_bytes'
    elif change == 'no_method': proof.pop('request_method')
    proof['source_url'] = url
    assert 'original_http_receipts' not in observation_details(entry)


def test_long_url_does_not_become_a_generic_component_exception_or_invent_a_send():
    from provider_observation_details import observation_details
    entry, url = captured_entry()
    entry.pop('http_request_sent')
    entry['component_statuses'] = {'same': {'url': url}}
    details = observation_details(entry)
    assert 'http_request_sent' not in details['original_http_receipts'][0]
    assert not details['component_statuses']['same']
