"""Show cohorts and overlapping causes without changing the quality decision."""
import json
import subprocess
from datetime import datetime
from pathlib import Path

from report_current_quality_summary import build_current_quality_summary
from test_quality_reason_classification import row

STATIC = Path(__file__).resolve().parents[1] / 'backend/static'


def render(payload):
    code = f"""
    global.window = {{}};
    const fs = require('fs'), vm = require('vm');
    for (const name of ['report_quality_evidence_helpers.js','quality_population_helpers.js','watchlist_current_quality_helpers.js','history_current_quality_helpers.js'])
        vm.runInThisContext(fs.readFileSync({json.dumps(str(STATIC))}+'/'+name,'utf8'));
    const payload = {json.dumps(payload)};
    const e = value => String(value).replaceAll('<','&lt;').replaceAll('>','&gt;');
    console.log(JSON.stringify({{
      watch: window.StockAgentWatchlistCurrentQualityHelpers.summary({{current_quality_summary:payload}}),
      history: window.StockAgentHistoricalCurrentQualityHelpers.render({{...payload,scope:'historical_filter_current_latest'}},e)
    }}));
    """
    return json.loads(subprocess.run(['node','-e',code],check=True,capture_output=True,text=True).stdout)


def test_both_quality_views_display_cohorts_overlap_and_warning_causes():
    payload = build_current_quality_summary([
        row('2026-10-27', ['v4_market_observation_stale'], ['v4_raw_fcf_period_unverified']),
        row('2026-10-26', ['v4_trade_reason_source_missing'])], scope='all_indexed_reports',
        now=datetime.fromisoformat('2026-10-27T12:00:00+08:00'))
    for text in render(payload).values():
        assert '股票×流程最新版 2 份' in text
        assert '今日版本 1、較舊 1' in text
        assert '原因分類（份數可重疊）' in text
        assert '分類不等於程式故障或誤攔判定' in text
        assert '即期FCF期間未核 1' in text


def test_invalid_cohort_totals_do_not_display_false_population():
    payload = build_current_quality_summary([row('2026-10-27')], scope='all_indexed_reports',
        now=datetime.fromisoformat('2026-10-27T12:00:00+08:00'))
    payload['report_date_cohorts']['counts']['today'] = 209
    for text in render(payload).values():
        assert '今日版本 209' not in text


def test_population_helper_loads_before_views_with_fresh_asset_versions():
    page = (STATIC/'index.html').read_text()
    helper = '/static/quality_population_helpers.js?v=20261027-session-quality-scope'
    assert helper in page
    for name in ('watchlist','history'):
        consumer = f'/static/{name}_current_quality_helpers.js?v=20261027-session-quality-scope'
        assert page.index(helper) < page.index(consumer)
