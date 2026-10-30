import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from market_screener_asof import build_source_dates
from market_screener_candidates import institutional_candidates, technical_candidates
from market_screener_sources import TwseFreeScreenerDataSource
from reporting.mode_focus_context import build_mode_focus_context
from reporting.mode_templates import build_mode_focus_markdown, get_report_template_profile


def test_missing_twse_date_does_not_become_scan_day():
    source = TwseFreeScreenerDataSource()
    scan_date = date(2026, 10, 1)
    source._json_get = lambda url: ([{'Code': '2330', 'ClosingPrice': '100', 'TradeVolume': '10000'}]
                                  if 'STOCK_DAY_ALL' in url else [{'Code': '2330', 'MonthlyAveragePrice': '80'}])
    daily = source.fetch_daily_frame(scan_date)
    institution = pd.DataFrame(source._institutional_records_from_payload(
        {'data': [['', '2330', '台積電', '3000', '1000']]}, 'Foreign_Investor', scan_date))
    assert daily.iloc[0]['date'] == ''
    assert institution.iloc[0]['date'] == ''
    assert technical_candidates(daily, scan_date=scan_date, top_n=10) == []
    assert institutional_candidates(institution, scan_date=scan_date, top_n=10) == []


def test_source_dates_exclude_future_and_keep_missing_and_old_distinct():
    result = build_source_dates(pd.DataFrame({'date': ['2026-09-30', None, '2026-10-02']}),
                                pd.DataFrame({'date': ['2026-10-01']}), scan_date=date(2026, 10, 1),
                                institutional_provider='FinMind', daily_provider='TWSE')
    assert result['both_sources_on_scan_date'] is False
    assert result['sources']['institutional'] == {
        'provider': 'FinMind', 'as_of': '2026-09-30', 'acquisition_completed_at': None, 'status': 'older_observation',
        'invalid_date_rows': 1, 'future_date_rows': 1}
    assert result['sources']['daily_prices']['status'] == 'scan_date_observed'


def test_report_exposes_actual_dates_instead_of_fetch_date():
    data = {'fetch_date': '2026-10-01', 'daily_market_data': {'as_of': '2026-10-01', 'source': 'yfinance'},
            'institutional_trading': {'observation_dates': ['2026-09-29', '2026-09-30'], 'source': 'FinMind'}}
    focus = build_mode_focus_context({'data': data}, {}, pipeline_id='v4')
    rendered = build_mode_focus_markdown(get_report_template_profile('v4'), focus)
    assert '2026-09-30（data.institutional_trading.observation_dates' in rendered
    assert '日期未對齊或缺漏' in rendered
    assert '分數不是上漲機率' in rendered
    missing = build_mode_focus_context({'data': {'fetch_date': '2026-10-01'}}, {}, pipeline_id='v4')
    assert '未確認' in missing['rows'][0]['value']
    assert not any(row['label'] == '行情觀測日' for row in build_mode_focus_context({'data': data}, {}, pipeline_id='v1')['rows'])
