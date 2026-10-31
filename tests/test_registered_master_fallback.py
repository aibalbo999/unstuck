"""The normal news provider must recover through complete official originals."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
import time
import pytest

from cache_backends import InMemoryCache
import cache_store
from data_fetch.issuer_news_provider import IssuerNewsProvider
from data_fetch.market_sources import registered_issuer_articles as source
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
from data_fetch.market_sources.official_issuer_master_transport import IssuerMasterHttp
from search_provider_runtime import SourceResponseError
from test_yulon_group_articles import setup, NOW, ARTICLES, DIRECTORY, INDEX
from test_official_issuer_master_json import json_value, RAW, JSON_URL

NATIVE_GET = source.ArticlesHttp.get


@pytest.fixture
def wire(monkeypatch):
    cache_store.set_cache_backend(InMemoryCache())
    h = setup(monkeypatch)
    article_get = source.ArticlesHttp.get
    calls = []
    control = {'failure': 'timeout', 'value': json_value()}

    def get(http, url):
        if url in (source.CSV_MASTER_URL, JSON_URL):
            return NATIVE_GET(http, url)
        return article_get(http, url)

    def download(http, url, diagnostic):
        calls.append(url)
        http.http_request_count += 1
        diagnostic.update(http_request_sent=True)
        if url == source.CSV_MASTER_URL:
            raise SourceResponseError(control['failure'])
        assert url == JSON_URL
        diagnostic['http_status'] = 200
        return deepcopy(control['value'])

    monkeypatch.setattr(source.ArticlesHttp, 'get', get)
    monkeypatch.setattr(IssuerNewsHttp, '_download', download)
    monkeypatch.setattr(IssuerMasterHttp, 'download_original', download)
    yield h, calls, control
    cache_store.reset_cache_store_for_tests()


def fetch(h):
    return IssuerNewsProvider().fetch(SimpleNamespace(ticker='2201.TW'), {'data': h.data})


def test_normal_news_recovers_csv_timeout_through_official_json(wire):
    h, calls, _ = wire
    result = fetch(h)
    assert result.status == 'success' and len(result.value) == 2, result.audit
    assert calls == [source.CSV_MASTER_URL, JSON_URL]
    assert result.audit['http_request_count'] == 6
    assert result.audit['component_receipts'][0]['error_kind'] == 'timeout'
    for row in result.value:
        proof = row['issuer_news_receipt']['source_record_archive']['master']
        assert proof['source_url'] == JSON_URL
        assert proof['raw_response_sha256'] == sha256(RAW).hexdigest()
        assert proof['evidence_kind'] == 'decoded_http_response_bytes'
        assert proof['wire_original'] and proof['acquisition_manifest']
        assert source.verified_record(row, h.data, today=datetime.fromtimestamp(NOW, timezone.utc).date())


@pytest.mark.parametrize('error', ['access_denied', 'rate_limited', 'authentication',
                                 'original_unverified', 'request_pacing'])
def test_terminal_master_errors_never_switch_endpoints(wire, error):
    h, calls, control = wire
    control['failure'] = error
    result = fetch(h)
    assert result.status == 'error' and not result.value
    assert calls == [source.CSV_MASTER_URL] and h.calls == []


@pytest.mark.parametrize('url', [source.CSV_MASTER_URL, JSON_URL])
def test_active_legacy_news_error_is_preserved_without_bypass(wire, url):
    h, calls, _ = wire
    key = 'shared_provider:v1:' + sha256(('issuer-news-raw:v1:' + url).encode()).hexdigest()
    value = {'error_kind': 'SourceResponseError', 'retry_after_epoch': NOW + 60,
             'fresh_until_epoch': NOW}
    cache_store.set_cache_json(key, value, ttl_seconds=60)
    result = fetch(h)
    assert result.status == 'error' and not result.value and h.calls == []
    assert JSON_URL not in calls
    assert cache_store.get_cache_json(key) == value


def test_warm_shared_json_preserves_epoch_and_only_fetches_four_news_pages(wire):
    h, calls, _ = wire
    first = fetch(h)
    second = fetch(h)
    assert first.status == second.status == 'success'
    assert calls == [source.CSV_MASTER_URL, JSON_URL]
    assert second.audit['http_request_count'] == 4
    before = first.value[0]['issuer_news_receipt']['source_record_archive']['master']
    after = second.value[0]['issuer_news_receipt']['source_record_archive']['master']
    assert after['cache_hit'] is True and after['retrieved_at'] == before['retrieved_at']
    assert after['fresh_until_epoch'] <= before['fresh_until_epoch']
    assert after['wire_original'] == before['wire_original']


def test_warm_json_does_not_hide_a_new_legacy_csv_news_refusal(wire, monkeypatch):
    h, calls, _ = wire
    assert fetch(h).status == 'success'
    # CSV's own failure reservation has expired, but JSON remains reusable.
    monkeypatch.setattr(time, 'time', lambda: NOW+121)
    key = 'shared_provider:v1:' + sha256(('issuer-news-raw:v1:' + source.CSV_MASTER_URL).encode()).hexdigest()
    refusal = {'error_kind':'SourceResponseError', 'retry_after_epoch':NOW+181,
               'fresh_until_epoch':NOW+121}
    cache_store.set_cache_json(key, refusal, ttl_seconds=60)
    calls.clear(); h.calls.clear()
    result = fetch(h)
    assert result.status == 'error' and not result.value
    assert not calls and not h.calls
    assert cache_store.get_cache_json(key) == refusal


def test_saved_news_replays_after_two_days_without_renewing_master(wire, monkeypatch):
    h, _, _ = wire
    result = fetch(h)
    before = deepcopy(result.value)
    monkeypatch.setattr(time, 'time', lambda: NOW + 2 * 86400)
    for row in result.value:
        assert source.verified_record(row, h.data, today=datetime.fromtimestamp(NOW + 2 * 86400, timezone.utc).date())
    assert result.value == before


@pytest.mark.parametrize('field', ['wire', 'manifest', 'url', 'policy', 'shorten_expiry', 'strip_markers', 'strip_and_relabel_legacy'])
def test_shared_master_tampering_cannot_downgrade_to_legacy_replay(wire, field):
    h, _, _ = wire
    row = deepcopy(fetch(h).value[0])
    receipt = row['issuer_news_receipt']
    proof = receipt['source_record_archive']['master']
    if field == 'wire':
        proof['wire_original']['raw_response_sha256'] = '0' * 64
    elif field == 'manifest':
        proof['acquisition_manifest']['raw_response_sha256'] = '0' * 64
    elif field == 'url':
        proof['source_url'] = source.CSV_MASTER_URL
    elif field == 'policy':
        receipt['policy'] = source.POLICY
    elif field == 'shorten_expiry':
        proof['fresh_until_epoch'] -= 1
    else:
        for k in ('retrieval_policy', 'response_metadata', 'acquisition_manifest', 'wire_original',
                  'fresh_until_epoch', 'reusable', 'request_body'):
            proof.pop(k, None)
        proof['evidence_kind'] = 'raw_http_response_bytes'
        if field == 'strip_and_relabel_legacy':
            receipt['policy'] = source.POLICY
            # Even an exact raw legacy shape may not claim a decoded JSON
            # response was an old uncompressed native original.
            from data_fetch.market_sources.official_issuer_master import ARCHIVE_FIELDS
            for k in set(proof) - ARCHIVE_FIELDS:
                proof.pop(k)
    assert source.verified_record(row, h.data, today=datetime.fromtimestamp(NOW, timezone.utc).date()) is None


def test_final_handoff_respects_shorter_shared_master_expiry(wire, monkeypatch):
    h, _, control = wire
    control['value'] = json_value(policy='max-age=1')
    original = source.verified_record
    count = [0]

    def verify(*args, **kwargs):
        result = original(*args, **kwargs)
        count[0] += 1
        if count[0] == 2:
            monkeypatch.setattr(time, 'time', lambda: NOW + 2)
        return result

    monkeypatch.setattr(source, 'verified_record', verify)
    result = fetch(h)
    assert result.status == 'error' and result.value == []
    assert result.audit['record_count'] == 0


def test_master_fallback_does_not_extend_the_whole_news_deadline(wire, monkeypatch):
    h, calls, _ = wire
    clock = [100.]
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    original = IssuerMasterHttp.download_original

    def late(http, url, diagnostic):
        try:
            return original(http, url, diagnostic)
        finally:
            clock[0] = 121.

    monkeypatch.setattr(IssuerMasterHttp, 'download_original', late)
    result = fetch(h)
    assert result.status == 'error' and result.value == []
    assert calls == [source.CSV_MASTER_URL] and not h.calls


@pytest.mark.parametrize('ticker', ['2464.TW', '2886.TW'])
def test_shared_master_fallback_applies_to_existing_registered_issuers(wire, monkeypatch, ticker):
    import test_registered_issuer_articles as existing
    h, calls, _ = wire
    with monkeypatch.context() as fixture_patch:
        other = existing.setup(fixture_patch, ticker)
    h.source.update(other.source)
    result = IssuerNewsProvider().fetch(SimpleNamespace(ticker=ticker), {'data': other.data})
    assert result.status in {'success', 'unavailable'}, result.audit
    assert calls == [source.CSV_MASTER_URL, JSON_URL]
    assert other.index in h.calls
    if ticker == '2886.TW':
        assert result.value
        assert all(row['issuer_news_receipt']['master_source_url'] == JSON_URL for row in result.value)
    else:
        # The September 15 fixture is genuinely outside October 16's window;
        # a working identity fallback must not relabel it as current news.
        assert not result.value and other.article not in h.calls
