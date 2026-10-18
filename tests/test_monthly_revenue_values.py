"""FinMind observations retain explicit zero without inventing missing amounts."""
import pandas as pd
import pytest

from data_fetch.types import FetchRequest
from data_fetch.taiwan_providers import MonthlyRevenueProvider


@pytest.fixture(autouse=True)
def isolated_cache():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


@pytest.fixture(params=['market_source', 'legacy_extractor', 'typed_provider'])
def collect(request, monkeypatch):
    from data_fetch.market_sources import taiwan
    from data_fetch import yfinance_extractors
    official_calls = []

    def official_fallback(ticker):
        official_calls.append(ticker)
        return {'value': [], 'audit': {
            'source': 'monthly_revenue', 'provider': 'fixture official',
            'status': 'unavailable', 'record_count': 0}}

    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue.fetch_official_monthly_revenue',
                        official_fallback)

    def fetch(rows):
        frame = pd.DataFrame(rows, dtype=object)
        before = frame.copy(deep=True)
        sdk_calls = []

        class Loader:
            def taiwan_stock_month_revenue(self, **kwargs):
                sdk_calls.append(kwargs)
                return frame

        monkeypatch.setattr(taiwan, 'DataLoader', Loader)
        if request.param == 'market_source':
            value, audit = taiwan.fetch_monthly_revenue_records('7799.TW', data_loader_cls=Loader)
        elif request.param == 'legacy_extractor':
            value, audit = yfinance_extractors.fetch_monthly_revenue_records('7799.TW', data_loader_cls=Loader)
        else:
            result = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('7799.TW'))
            value, audit = result.value, result.audit
        assert len(sdk_calls) == 1 and sdk_calls[0]['stock_id'] == '7799'
        pd.testing.assert_frame_equal(frame, before)
        return value, audit, official_calls

    return fetch


def rows_for(values):
    return [{'stock_id': '7799', 'revenue_year': 2026, 'revenue_month': month, 'revenue': value}
            for month, value in enumerate(values, 4)]


def test_six_months_keep_the_three_explicit_zero_amounts(collect):
    # Amounts corroborated by the 2026-10-13 TWSE original; SDK itself is mocked.
    value, audit, official = collect(rows_for([0, 504000, 0, 0, 334000, 1105000]))
    assert value == [f'2026年{m}月: NT${v / 1e8:.2f}億'
                     for m, v in zip(range(4, 10), [0, 504000, 0, 0, 334000, 1105000])]
    assert audit['status'] == 'success' and audit['record_count'] == 6
    assert official == []


def test_all_zero_months_are_real_observations_and_do_not_trigger_fallback(collect):
    value, audit, official = collect(rows_for([0] * 6))
    assert value == [f'2026年{m}月: NT$0.00億' for m in range(4, 10)]
    assert audit['status'] == 'success' and audit['record_count'] == 6
    assert official == []


def test_missing_nonfinite_and_boolean_amounts_are_not_zero_observations(collect):
    value, audit, official = collect(rows_for([None, float('nan'), float('inf'), True, 0, -100000000]))
    assert value == ['2026年8月: NT$0.00億', '2026年9月: NT$-1.00億']
    assert audit['record_count'] == 2 and official == []


def test_invalid_calendar_periods_do_not_become_revenue_records(collect):
    rows = rows_for([100000000] * 6)
    rows[0]['revenue_month'] = 13
    rows[1]['revenue_month'] = 1.5
    rows[2]['revenue_year'] = float('nan')
    rows[3]['revenue_year'] = True
    rows[4]['revenue_year'] = '2026'
    rows[4]['revenue_month'] = '8'
    value, audit, official = collect(rows)
    assert value == ['2026年8月: NT$1.00億', '2026年9月: NT$1.00億']
    assert audit['record_count'] == 2 and official == []


def test_zero_fix_keeps_existing_last_six_row_window(collect):
    rows = [{'stock_id': '7799', 'revenue_year': 2026, 'revenue_month': 3, 'revenue': 900000000}]
    rows += rows_for([100000000] * 6)
    value, audit, official = collect(rows)
    assert value == [f'2026年{m}月: NT$1.00億' for m in range(4, 10)]
    assert audit['record_count'] == 6 and official == []
