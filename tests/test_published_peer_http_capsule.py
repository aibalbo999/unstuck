"""Only a fully consumed native response can supply original HTTP provenance."""
import json
from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256

import httpx
import pytest

from test_yahoo_published_peer_ranking import page, master


def native_fetch(monkeypatch, *, response_change=None, raw_override=None, proxy=None):
    from data_fetch.market_sources import yahoo_peer_ranking as ranking
    today = ranking._today()
    raw = page(today) if raw_override is None else raw_override
    calls = []

    def respond(request):
        calls.append(request)
        response = httpx.Response(200, stream=httpx.ByteStream(raw), request=request,
                                  headers={'content-type': 'text/html; charset=utf-8',
                                           'content-length': str(len(raw))})
        return response

    client = httpx.Client(transport=httpx.MockTransport(respond))
    class ClientBoundary:
        @contextmanager
        def stream(self, *args, **kwargs):
            with client.stream(*args, **kwargs) as response:
                # HTTPX normalizes request/history after its transport returns;
                # mutate at the external client boundary actually read by us.
                if response_change:
                    response_change(response)
                yield response

        def close(self):
            client.close()

    monkeypatch.setattr(ranking.httpx, 'Client', lambda **kwargs: ClientBoundary())
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.delenv(name, raising=False)
    if proxy:
        monkeypatch.setenv('HTTPS_PROXY', proxy)
    result = ranking.fetch_published_industry_peers('2882.TW', today=today,
                                                    master_rows=master(today))
    assert len(calls) == 1
    return result, raw


def test_native_complete_response_binds_immutable_original_and_projected_flags(monkeypatch):
    from official_response_evidence import read_response
    from provider_observation_details import observation_details

    value, raw = native_fetch(monkeypatch)
    receipt = value['raw_http_receipt']
    assert receipt.get('http_status_observed') is True
    assert receipt.get('response_complete') is True
    assert receipt.get('cache_hit') is False
    assert receipt.get('request_method') == 'GET'
    capsule = json.loads(read_response(receipt['native_http_manifest'], max_bytes=16384))
    assert capsule['body_sha256'] == sha256(raw).hexdigest()
    assert capsule['body_bytes'] == len(raw)
    assert capsule['received_at'] == receipt['retrieved_at']
    assert capsule['stream_consumed'] is True
    details = observation_details({'raw_http_receipt': receipt, 'http_request_sent': True,
                                   'cache_hit': False})
    projected = details['original_http_receipts'][0]
    assert projected['response_complete'] is True
    assert projected['http_status_observed'] is True
    assert projected['original_cache_hit'] is False
    assert projected['response_sha256'] == sha256(raw).hexdigest()
    assert 'raw_response_path' not in json.dumps(details)


@pytest.mark.parametrize('mode', ['wrong_url', 'wrong_method', 'cache_attribute',
    'cache_extension', 'cache_extension_string', 'cache_extension_integer',
    'redirect', 'authorization', 'cookie', 'proxy_authorization',
    'content_range', 'empty_content_range', 'float_status', 'length', 'mime', 'encoding'])
def test_native_unqualified_response_never_gets_a_valid_capsule(monkeypatch, mode):
    from data_fetch.market_sources.yahoo_peer_ranking import RankingError

    def change(response):
        if mode == 'wrong_url':
            response._request = httpx.Request('GET', 'https://example.com/compare')
        elif mode == 'wrong_method':
            response._request = httpx.Request('POST', str(response.url))
        elif mode == 'cache_attribute': response.from_cache = True
        elif mode == 'cache_extension': response.extensions['from_cache'] = True
        elif mode == 'cache_extension_string': response.extensions['from_cache'] = 'false'
        elif mode == 'cache_extension_integer': response.extensions['from_cache'] = 1
        elif mode == 'redirect': response.history = [httpx.Response(302)]
        elif mode in ('authorization', 'cookie', 'proxy_authorization'):
            response.request.headers[mode.replace('_', '-')] = 'private-do-not-archive'
        elif mode == 'content_range': response.headers['content-range'] = 'bytes 0-1/1000'
        elif mode == 'empty_content_range': response.headers['content-range'] = ''
        elif mode == 'float_status': response.status_code = 200.0
        elif mode == 'length': response.headers['content-length'] = '1'
        elif mode == 'mime': response.headers['content-type'] = 'application/json'
        elif mode == 'encoding': response.headers['content-encoding'] = 'unknown'

    with pytest.raises(RankingError, match='source_native_receipt_invalid'):
        native_fetch(monkeypatch, response_change=change)


@pytest.mark.parametrize('mode', ['remove_manifest', 'remove_flag', 'false_flag',
    'changed_epoch', 'changed_length', 'changed_manifest_size', 'wrong_manifest_type'])
def test_saved_manifest_binds_metadata_and_cannot_upgrade_legacy(monkeypatch, mode):
    from data_fetch.market_sources import yahoo_peer_ranking as ranking
    value, _ = native_fetch(monkeypatch)
    value = deepcopy(value)
    receipt = value['raw_http_receipt']
    if mode == 'remove_manifest': receipt.pop('native_http_manifest')
    elif mode == 'remove_flag': receipt.pop('response_complete')
    elif mode == 'false_flag': receipt['response_complete'] = False
    elif mode == 'changed_epoch': receipt['retrieved_at'] -= 1
    elif mode == 'changed_length': receipt['raw_response_bytes'] -= 1
    elif mode == 'changed_manifest_size': receipt['native_http_manifest']['raw_response_bytes'] -= 1
    elif mode == 'wrong_manifest_type': receipt['native_http_manifest']['evidence_kind'] = 'raw_http_response_bytes'
    with pytest.raises(ranking.RankingError, match='source_receipt_invalid'):
        ranking.validate_stored_ranking_body(value, '2882.TW', master(ranking._today()),
                                             today=ranking._today())


def test_legacy_metadata_remains_unknown_instead_of_becoming_a_native_success(monkeypatch):
    from data_fetch.market_sources import yahoo_peer_ranking as ranking
    from data_fetch.market_sources.published_peer_http_capsule import validate_native_receipt, FLAGS
    from provider_observation_details import observation_details
    value, _ = native_fetch(monkeypatch)
    original_epoch = value['raw_http_receipt']['retrieved_at']
    receipt = value['raw_http_receipt']
    for key in (*FLAGS, 'native_http_manifest'): receipt.pop(key)
    ranking.validate_stored_ranking_body(value, '2882.TW', master(ranking._today()),
                                         today=ranking._today())
    assert validate_native_receipt(receipt, '2882.TW') is False
    projected = observation_details({'raw_http_receipt': receipt})['original_http_receipts'][0]
    assert not {'response_complete', 'http_status_observed', 'original_cache_hit'} & projected.keys()
    assert receipt['retrieved_at'] == original_epoch


def test_injected_client_does_not_claim_original_native_http(monkeypatch):
    from data_fetch.market_sources import yahoo_peer_ranking as ranking
    today = ranking._today()
    with httpx.Client(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, content=page(today)))) as client:
        result = ranking.fetch_published_industry_peers('2882.TW', today=today,
                                                       master_rows=master(today), client=client)
    assert not {'native_http_manifest', 'response_complete', 'cache_hit',
                'http_status_observed'} & result['raw_http_receipt'].keys()


def test_configured_proxy_does_not_create_unqualified_native_flags(monkeypatch):
    value, _ = native_fetch(monkeypatch, proxy='http://127.0.0.1:9999')
    assert 'native_http_manifest' not in value['raw_http_receipt']
    assert 'response_complete' not in value['raw_http_receipt']


def test_failed_manifest_archive_cannot_deliver_native_success(monkeypatch):
    from data_fetch.market_sources import published_peer_http_capsule as capsule
    from data_fetch.market_sources.yahoo_peer_ranking import RankingError
    monkeypatch.setattr(capsule, 'archive_response', lambda *a, **kw: {'status': 'unavailable'})
    with pytest.raises(RankingError, match='source_native_receipt_invalid'):
        native_fetch(monkeypatch)


@pytest.mark.parametrize('mode', ['read_timeout', 'oversize'])
def test_unfinished_stream_cannot_create_a_complete_original(monkeypatch, mode):
    from data_fetch.market_sources import yahoo_peer_ranking as ranking
    calls = []
    monkeypatch.setattr(ranking, 'archive_response', lambda *a, **kw: calls.append(kw))
    if mode == 'oversize':
        with pytest.raises(ranking.RankingError, match='size limit'):
            native_fetch(monkeypatch, raw_override=b'x' * 1_000_001)
    else:
        class BrokenStream(httpx.SyncByteStream):
            def __iter__(self):
                yield b'<html>'
                raise httpx.ReadTimeout('bounded interrupted stream')
        def change(response): response.stream = BrokenStream()
        with pytest.raises(httpx.ReadTimeout):
            native_fetch(monkeypatch, response_change=change)
    assert not calls


def test_native_cold_and_warm_sql_keep_original_epoch_and_one_acquisition(monkeypatch):
    from data_fetch.market_sources import yahoo_peer_ranking as ranking, peer_recovery
    from data_fetch.enrichment_search_providers import YahooPublishedPeerRankingProvider
    from data_fetch.types import FetchRequest
    from provider_observation_details import observation_details
    from provider_acquisition import get_provider_acquisition_summary
    from provider_sla import record_source_audit_entries
    value, raw = native_fetch(monkeypatch)
    epoch = value['raw_http_receipt']['retrieved_at']
    monkeypatch.setattr(peer_recovery, 'load_peer_stock_master', lambda: master(ranking._today()))
    calls = []
    def captured(*args, **kwargs):
        calls.append(args)
        return value
    monkeypatch.setattr(ranking, 'fetch_published_industry_peers', captured)
    provider = YahooPublishedPeerRankingProvider()
    request = FetchRequest.from_ticker('2882.TW')
    cold = provider.fetch(request)
    warm = provider.fetch(request)
    assert len(calls) == 1
    assert cold.status == 'success' and warm.status == 'skipped_fresh_cache'
    assert cold.audit['raw_http_receipt'] == warm.audit['raw_http_receipt']
    assert warm.audit['raw_http_receipt']['retrieved_at'] == epoch
    record_source_audit_entries([cold.audit, warm.audit])
    summary = get_provider_acquisition_summary('all')['sources'][0]
    assert summary['fetch_attempts'] == summary['fetched_count'] == 1
    assert summary['fresh_cache_count'] == 1
    projected = observation_details(warm.audit)['original_http_receipts'][0]
    assert projected['response_complete'] is True and projected['original_cache_hit'] is False
    assert projected['cache_hit'] is True and projected['http_request_sent'] is False
    assert projected['original_retrieved_at_epoch'] == epoch
    assert projected['response_sha256'] == sha256(raw).hexdigest()
    assert 'native_http_manifest' not in json.dumps(observation_details(cold.audit))
