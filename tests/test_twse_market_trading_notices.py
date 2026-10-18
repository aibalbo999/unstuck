"""A full market original may serve many issuers without inventing acquisitions."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import base64
import json
import time

import pytest

RAW = (Path(__file__).parent / 'fixtures/source_acquisition/twse_allmarket_notices_20261014.json').read_bytes()
NOW = datetime(2026, 10, 14, 4, 5, tzinfo=ZoneInfo('Asia/Taipei'))


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW.timestamp())
    yield
    cache_store.reset_cache_store_for_tests()


def test_public_provider_shares_one_full_original_and_keeps_target_identity(monkeypatch):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from data_fetch.trading_notices_provider import TradingNoticesProvider
    from data_fetch.types import FetchRequest
    from source_content_selection import issuer_match
    import data_fetch.market_sources.twse_trading_notices as legacy

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(legacy, 'datetime', FrozenDateTime)
    try:
        import data_fetch.market_sources.twse_market_trading_notices as market
        monkeypatch.setattr(market, 'datetime', FrozenDateTime)
    except ModuleNotFoundError:
        pass  # Before the feature, exercise the real individual-query provider.
    calls = []

    def download(self, url, diagnostic):
        calls.append(url)
        self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=200)
        return {'url': url, 'body_b64': base64.b64encode(RAW).decode(), 'sha256': sha256(RAW).hexdigest()}

    monkeypatch.setattr(IssuerNewsHttp, '_download', download)
    results = [TradingNoticesProvider().fetch(FetchRequest.from_ticker(t), {'data': {'ticker': t}})
               for t in ('6504.TW', '6531.TW', '1216.TW')]
    first, second, empty = results
    assert first.status == 'success' and first.value
    assert second.status == 'skipped_fresh_cache' and second.value
    assert len(calls) == 1 and 'querytype=1' in calls[0]
    assert first.audit['http_request_count'] == 1
    assert second.audit['http_request_count'] == empty.audit['http_request_count'] == 0
    assert empty.status == 'unavailable' and empty.value == []
    assert empty.audit['record_count'] == 0 and empty.audit['cache_hit'] is True
    assert first.audit['fetched_at_epoch'] == second.audit['fetched_at_epoch'] == empty.audit['fetched_at_epoch']
    for ticker, result in zip(('6504.TW', '6531.TW'), results):
        assert all(r['ticker'] == ticker and issuer_match(r, {'ticker': ticker}) == ticker.split('.')[0]
                   for r in result.value)
        assert all(r['trading_notice_receipt']['original']['raw_response_sha256'] == sha256(RAW).hexdigest()
                   for r in result.value)

    from provider_acquisition import observation_kind
    kinds = [observation_kind(dict(provider=r.audit['provider'], status=r.status,
                                  record_count=r.audit['record_count'], message=r.audit['message'],
                                  details=r.audit)) for r in results]
    assert kinds == ['fetched_count', 'fresh_cache_count', 'empty_cache_count']


@pytest.mark.parametrize('change', ['truncated', 'security_count', 'date_group', 'group_size',
                                  'query', 'unknown_markup', 'duplicate_day'])
def test_damage_anywhere_in_market_original_rejects_target_selection(change):
    from data_fetch.market_sources.twse_market_trading_notices import fetch_market_trading_notices
    p = json.loads(RAW)
    other = next(r for r in p['data'] if r[1] != '6504')
    if change == 'truncated':
        p['data'].pop()
    elif change == 'security_count':
        p['count'] += 1
    elif change == 'date_group':
        other[0] += 1
    elif change == 'group_size':
        other[3] = str(int(other[3]) + 1)
    elif change == 'query':
        p['params']['stockNo'] = '6504'
    elif change == 'unknown_markup':
        other[4] += '<script>bad()</script>'
    else:
        p['data'].append(deepcopy(other))
        p['total'] += 1
    records, audit = fetch_market_trading_notices('6504.TW', now=NOW,
        get=lambda url: json.dumps(p, ensure_ascii=False).encode())
    assert records == [] and audit['status'] == 'error' and audit['record_count'] == 0


@pytest.mark.parametrize('change', ['issuer', 'row_index', 'summary', 'missing_original', 'future_epoch'])
def test_saved_full_original_cannot_be_reassigned_or_modified(change):
    from data_fetch.market_sources.twse_market_trading_notices import fetch_market_trading_notices
    from source_content_selection import issuer_match
    records, _ = fetch_market_trading_notices('6504.TW', now=NOW, get=lambda url: RAW)
    record = deepcopy(records[0])
    if change == 'issuer':
        record['ticker'] = '6531.TW'
    elif change == 'row_index':
        record['trading_notice_receipt']['row_index'] = next(i for i, r in enumerate(json.loads(RAW)['data']) if r[1] == '6531')
    elif change == 'summary':
        record['summary'] += '價格保證上漲'
    elif change == 'missing_original':
        record['trading_notice_receipt'].pop('original')
    else:
        record['trading_notice_receipt']['original']['retrieved_at'] += 1
    assert issuer_match(record, {'ticker': record['ticker']}) is None


@pytest.mark.parametrize('expired', ['deadline', 'ttl'])
def test_last_record_validation_cannot_outlive_total_budget_or_original_ttl(monkeypatch, expired):
    import data_fetch.market_sources.twse_market_trading_notices as market
    wall, mono = [NOW.timestamp()], [0.]
    monkeypatch.setattr(time, 'time', lambda: wall[0])
    monkeypatch.setattr(time, 'monotonic', lambda: mono[0])
    verify = market.verified_market_record
    count = sum(r[1] == '6504' for r in json.loads(RAW)['data'])
    seen = []
    def final_validation(*args):
        value = verify(*args)
        seen.append(value)
        if len(seen) == count:
            if expired == 'deadline':
                mono[0] = 8.
            else:
                wall[0] += 1800
        return value
    monkeypatch.setattr(market, 'verified_market_record', final_validation)
    records, audit = market.fetch_market_trading_notices('6504.TW', now=NOW, get=lambda url: RAW)
    assert len(seen) == count and records == []
    assert audit['status'] == 'error' and audit['record_count'] == 0 and audit['cache_hit'] is False


@pytest.mark.parametrize('status,kind', [(403, 'access_denied'), (429, 'rate_limited')])
def test_provider_failure_and_cooldown_never_become_success(monkeypatch, status, kind):
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from data_fetch.market_sources.twse_market_trading_notices import fetch_market_trading_notices
    from search_provider_runtime import SourceResponseError
    from provider_acquisition import observation_kind
    calls = []
    def fail(self, url, diagnostic):
        calls.append(url)
        self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=status)
        raise SourceResponseError(kind, status_code=status)
    monkeypatch.setattr(IssuerNewsHttp, '_download', fail)
    results = [fetch_market_trading_notices(t, now=NOW) for t in ('6504.TW', '6531.TW')]
    assert len(calls) == 1 and all(r == [] and a['status'] == 'error' for r, a in results)
    first, second = [a for _, a in results]
    assert first['http_status'] == status and first['error_kind'] == kind
    assert first['http_request_count'] == 1 and second['http_request_count'] == 0
    assert [observation_kind(dict(provider=a['provider'], status=a['status'], record_count=0,
                                  message=a['message'], details=a)) for a in (first, second)] == ['failed_count', 'local_block_count']
