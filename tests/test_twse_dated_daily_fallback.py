"""Public boundary checks. Original private-data replay cases remain local."""
from datetime import date
import pytest
import pandas as pd
from market_screener_sources import TwseFreeScreenerDataSource, first_available_frame
from screener_twse_daily import DATED_URL

def payload(day='20261002', volume='33,115,055', close='68.30'):
    return {'stat': 'OK', 'date': day, 'tables': [{'fields': ['證券代號', '證券名稱', '成交股數', '收盤價'], 'data': [['1301', '台塑', volume, close], ['0050', 'ETF', '100', '100']]}]}

def source(*, primary_day='1151001', fallback=None, average_day='1151001', failure=False):
    s = TwseFreeScreenerDataSource()
    s._json_get = lambda url: [{'Date': average_day, 'Code': '1301', 'MonthlyAveragePrice': '66.80'}] if 'AVG' in url else [{'Date': primary_day, 'Code': '1301', 'Name': '台塑', 'ClosingPrice': '66.80', 'TradeVolume': '19,100,785'}]
    calls = []

    def get(url, params):
        calls.append((url, params))
        if failure:
            raise RuntimeError('temporary source unavailable')

        class Response:

            def json(self):
                return fallback if fallback is not None else payload()
        return Response()
    s._get = get
    return (s, calls)

def test_current_day_rwd_recovers_stale_feed_and_ignores_prior_average():
    s, calls = source()
    warnings = []
    frame, provider = first_available_frame([s], 'daily', lambda item: item.fetch_daily_frame(date(2026, 10, 2)), warnings)
    row = frame[frame.stock_id == '1301'].iloc[0]
    assert row['date'] == '2026-10-02' and row['close'] == 68.3 and (row['Trading_Volume'] == 33115055)
    assert pd.isna(row['monthly_average_close'])
    assert row['latest_volume_unit'] == 'shares' and 'date=20261002' in row['price_source_url']
    assert calls[0][0] == DATED_URL and calls[0][1]['date'] == '20261002'
    assert {'openapi_daily_date_mismatch', 'dated_daily_fallback_used', 'monthly_average_date_not_matched'} <= {x['code'] for x in warnings}

@pytest.mark.parametrize('bad', [payload('20261001'), payload('20261003'), {'stat': 'OK', 'tables': []}, {'stat': 'no data', 'date': '20261002'}])
def test_wrong_missing_or_future_fallback_date_never_relabels_primary(bad):
    s, calls = source(fallback=bad)
    frame = s.fetch_daily_frame(date(2026, 10, 2))
    assert frame.iloc[0]['date'] == '2026-10-01'
    assert 'dated_daily_not_verified' in [x['code'] for x in frame.attrs['source_warnings']]

def test_transient_fallback_failure_is_visible_and_later_call_can_recover():
    s, _ = source(failure=True)
    before = s.fetch_daily_frame(date(2026, 10, 2))
    assert before.iloc[0]['date'] == '2026-10-01'
    assert 'dated_daily_unavailable' in [x['code'] for x in before.attrs['source_warnings']]
    recovered, _ = source()
    assert recovered.fetch_daily_frame(date(2026, 10, 2)).iloc[0]['date'] == '2026-10-02'

def test_weekend_uses_last_verified_session_not_saturday():
    s, calls = source()
    frame = s.fetch_daily_frame(date(2026, 10, 3))
    assert frame.iloc[0]['date'] == '2026-10-02' and calls[0][1]['date'] == '20261002'

def test_current_primary_avoids_fallback_and_missing_prices_stay_unknown():
    s, calls = source(primary_day='1151002', average_day='1151002')
    frame = s.fetch_daily_frame(date(2026, 10, 2))
    assert calls == [] and frame.attrs['source_warnings'] == []
    s, _ = source(fallback=payload(volume='--', close='--'))
    frame = s.fetch_daily_frame(date(2026, 10, 2))
    assert pd.isna(frame.iloc[0]['close']) and pd.isna(frame.iloc[0]['Trading_Volume'])
