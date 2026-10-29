from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from curl_cffi.requests import Session
import provider_sla
REAL_RECORD = provider_sla.record_source_audit_entries
import yfinance_transport_receipts as observer
from provider_correlation import correlation_scope, source_operation


@pytest.fixture
def transport(monkeypatch):
    events = []
    monkeypatch.setattr(provider_sla, 'record_source_audit_entries', lambda rows: events.extend(rows))
    monkeypatch.setattr(Session, '_request_once', lambda self, method, url, **kw: SimpleNamespace(
        url=url, status_code=200, content=b'private-body', from_cache=kw.get('cached', False)))
    session = Session()
    observer.observe_session(session)
    monkeypatch.setattr(observer, 'observe_yfinance', lambda: observer.observe_session(session))
    return session, events


def request(session, symbol='SPY', **kw):
    return session._request_once('GET', 'https://query1.finance.yahoo.com/v8/finance/chart/' + symbol, **kw)


def test_selected_global_proxy_is_transport_only_and_preserves_response(transport):
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW', fetch_id='global-fetch'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy('SPY'):
                response = request(session)
    row, = events
    assert response.content == b'private-body'
    assert row['source'] == 'global_market_context' and row['ticker'] == '2330.TW'
    assert row['fetch_id'] == 'global-fetch' and row['operation_id']
    assert row['record_count'] == 0 and row['selection_policy'] == 'transport-receipt-only:v1'
    assert 'SPY' in row['message'] and 'private-body' not in str(events)


@pytest.mark.parametrize('selected,actual', [('SPY', 'QQQ'), ('SPY', '2330.TW'), ('OTHER', 'OTHER')])
def test_other_symbol_cannot_borrow_proxy_scope(transport, selected, actual):
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy(selected):
                request(session, actual)
    assert not events


@pytest.mark.parametrize('source,provider', [('market_data', 'yfinance global context'),
    ('global_market_context', 'unrelated provider')])
def test_other_source_operation_is_not_attributed(transport, source, provider):
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation(source, provider):
            with observer.observe_global_proxy('SPY'):
                request(session)
    assert not events


def test_nested_operation_and_cached_response_are_not_native_samples(transport):
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy('SPY'):
                request(session, cached=True)
                with source_operation('global_market_context', 'yfinance global context'):
                    request(session)
            request(session)
    assert not events


def test_parallel_proxy_scopes_do_not_cross_attribute(transport):
    session, events = transport
    def run(symbol):
        with correlation_scope(replace=True, ticker='2330.TW', fetch_id=symbol):
            with source_operation('global_market_context', 'yfinance global context'):
                with observer.observe_global_proxy(symbol):
                    request(session, symbol)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(run, ['SPY', 'QQQ']))
    assert len(events) == 2
    assert all(row['fetch_id'] in row['message'] for row in events)


def test_real_collector_installs_scoped_observation_before_sdk_history(transport, monkeypatch):
    import pandas as pd
    from data_fetch.market_sources import global_context
    session, events = transport
    class Stock:
        def history(self, **kwargs):
            request(session, '%5ETNX')
            return pd.DataFrame({'Close': [4.1, 4.2]})
    monkeypatch.setattr(global_context.yf, 'Ticker', lambda symbol: Stock())
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            value = global_context.fetch_global_market_context('2330.TW', symbols=[('^TNX', 'rate', 'rates')])
    assert value['items'][0]['latest'] == 4.2 and len(events) == 1
    assert events[0]['source'] == 'global_market_context' and '^TNX' in events[0]['message']


@pytest.mark.parametrize('path', ['/v10/finance/quoteSummary/SPY', '/v7/finance/quote?symbols=SPY'])
def test_global_history_scope_does_not_cover_other_sdk_routes(transport, path):
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy('SPY'):
                session._request_once('GET', 'https://query1.finance.yahoo.com' + path)
    assert not events


def test_exception_and_nested_invalid_scope_do_not_leak(transport):
    session, events = transport
    error = RuntimeError('same exception')
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with pytest.raises(RuntimeError) as caught:
                with observer.observe_global_proxy('SPY'):
                    with observer.observe_global_proxy('UNKNOWN'):
                        request(session)
                    raise error
            request(session)
    assert caught.value is error and not events


def test_transport_receipt_does_not_add_acquisition_success_or_failure(transport, monkeypatch, tmp_path):
    from provider_acquisition import get_provider_acquisition_summary
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy('SPY'):
                request(session)
    monkeypatch.setattr(provider_sla, 'TASK_DB_PATH', str(tmp_path / 'audit.sqlite3'))
    REAL_RECORD(events)
    summary = get_provider_acquisition_summary('last_24h')
    row, = summary['sources']
    assert row['source'] == 'global_market_context' and row['http_attempt_count'] == 1
    assert row['fetch_attempts'] == row['fetched_count'] == row['failed_count'] == 0


def test_existing_failure_denominator_and_acquisition_rate_are_preserved(transport, monkeypatch, tmp_path):
    from provider_acquisition import get_provider_acquisition_summary
    session, events = transport
    monkeypatch.setattr(provider_sla, 'TASK_DB_PATH', str(tmp_path / 'audit.sqlite3'))
    REAL_RECORD([{'source': 'global_market_context', 'provider': 'yfinance global context',
        'status': status, 'record_count': count} for status, count in [('success', 2), ('error', 0)]])
    before, = get_provider_acquisition_summary()['sources']
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy('SPY'):
                request(session)
    REAL_RECORD(events)
    after, = get_provider_acquisition_summary()['sources']
    for field in ['fetched_count', 'failed_count', 'fetch_attempts', 'nonempty_rate']:
        assert after[field] == before[field]
    assert before['failed_count'] == 1 and before['nonempty_rate'] == 0.5
    assert after['http_attempt_count'] == before['http_attempt_count'] + 1


def test_changed_target_ticker_cannot_reuse_proxy_owner(transport):
    session, events = transport
    with correlation_scope(replace=True, ticker='2330.TW'):
        with source_operation('global_market_context', 'yfinance global context'):
            with observer.observe_global_proxy('SPY'):
                with correlation_scope(ticker='2317.TW'):
                    request(session)
    assert not events
