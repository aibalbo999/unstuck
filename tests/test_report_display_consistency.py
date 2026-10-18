"""Presentation fixes must not turn observations or missing values into trades."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))


def javascript(expression):
    files = ['ui_helpers.js', 'history_panel_helpers.js', 'report_preview_tracking_helpers.js',
             'history_panel_renderers.js']
    script = 'global.window = {StockAgentUiDataTrust: {}};\n'
    script += '\n'.join(f'require({json.dumps(str(ROOT/"backend/static"/name))});' for name in files)
    script += '\nprocess.stdout.write(JSON.stringify('+expression+'));'
    result = subprocess.run(['node', '-e', script], check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('label', ['Neutral', '中性 Neutral', '中性觀望', '觀望（暫不建立新交易）'])
def test_frontend_observation_is_never_labeled_as_a_holding(label):
    result = javascript(f'window.StockAgentUi.normalizeRecommendation({json.dumps(label)})')
    assert result == '觀望'
    assert javascript(f'window.StockAgentUi.recommendationTone({json.dumps(label)})') == 'is-neutral'


def test_real_holding_and_directional_recommendations_keep_their_meaning():
    assert javascript("['持有', 'Hold', '買入', '放空', '避免'].map(window.StockAgentUi.normalizeRecommendation)") == [
        '持有', '持有', '買入', '放空', '避免']


@pytest.mark.parametrize('value', [None, '', '   ', True, False, [], {}])
def test_non_numeric_tracking_inputs_do_not_become_zero(value):
    encoded = json.dumps(value)
    result = javascript(f'''[window.StockAgentHistoryPanelHelpers, window.StockAgentReportPreviewTrackingHelpers]
        .map(helper => [helper.formatNumber({encoded}), helper.formatPct({encoded})])''')
    assert result == [['尚未確認', '尚未確認'], ['尚未確認', '尚未確認']]


def test_actual_zero_return_is_distinct_from_missing_target_gap():
    result = javascript('''window.StockAgentReportPreviewTrackingHelpers.trackingView({
        status: 'tracked', initial_price: null, latest_price: null, return_pct: null,
        target_12m: null, target_12m_gap_pct: null})''')
    assert result['latestText'] == '尚未確認'
    assert result['returnText'] == '尚未確認'
    assert result['gapText'] == '尚未確認（未提供可比較的目標價）'
    assert javascript('window.StockAgentReportPreviewTrackingHelpers.formatPct(0)') == '0.00%'


def test_short_term_preview_does_not_imply_a_twelve_month_target():
    result = javascript('''window.StockAgentReportPreviewTrackingHelpers.trackingView({
        status: 'tracked', initial_price: 100, latest_price: 101, return_pct: 1,
        target_12m: null, target_12m_gap_pct: null}, {kind: 'swing_trade'})''')
    assert result['gapText'] == '不適用（短線模式不比較12個月目標）'


def test_missing_latest_price_is_not_misdiagnosed_as_a_missing_target():
    result = javascript('''window.StockAgentReportPreviewTrackingHelpers.trackingView({
        status: 'tracked', target_12m: 100, latest_price: null, target_12m_gap_pct: null})''')
    assert result['gapText'] == '尚未確認（未取得可比較的最新股價）'


def test_history_target_cell_does_not_render_missing_price_as_zero():
    result = javascript('''window.StockAgentHistoryPanelHelpers.targetComparisonCell(
        {target_12m: null, target_comparisons: {target_12m: {target: null, status: 'unavailable', gap_pct: null}}},
        'target_12m', window.StockAgentUi.escapeHtml)''')
    assert '尚未確認' in result
    assert 'tracking-target-value">0<' not in result


def test_swing_preview_has_same_observation_and_not_applicable_prices_as_report():
    from report_preview import build_report_preview
    snapshot = {'data': {'current_price': 100}, 'rerun_context': {'parsed': {'trade_setup': {
        'trade_direction': 'Neutral', 'entry_zone': 'N/A', 'target_price': None, 'stop_loss': '--',
        'core_catalyst': '等待法人轉買後再評估', 'risk_level': 'High'}}}}
    before = deepcopy(snapshot)
    result = build_report_preview('v4', '3017.TW', {'recommendation': '持有'}, snapshot=snapshot)
    assert result['primary'] == {'label': '交易方向', 'value': '觀望（暫不建立新交易）', 'tone': 'is-neutral'}
    assert all(item['value'] == '不適用（觀望中，暫不設定交易價位）' for item in result['targets'])
    assert all(item['missing_category'] == 'not_applicable' for item in result['targets'])
    assert all(item['missing_reason'] for item in result['targets'])
    assert snapshot == before


@pytest.mark.parametrize(('value', 'category'), [
    ('未提供，原分析未列目標', 'not_provided'),
    ('未確認，尚待事件日期', 'unconfirmed'),
    ('來源異常（官方服務逾時）', 'source_error'),
    ('不適用（本次不建立交易）', 'not_applicable'),
    ('N/A（未評估；缺少同期間可驗證目標）', 'unconfirmed'),
    ('N/A（來源異常：官方服務逾時）', 'source_error'),
])
def test_preview_retains_explicit_missing_category_and_reason(value, category):
    from report_preview import build_report_preview
    snapshot = {'rerun_context': {'parsed': {'trade_setup': {
        'trade_direction': 'Long', 'target_price': value}}}}
    result = build_report_preview('v4', '3017.TW', {}, snapshot=snapshot)
    target = result['targets'][1]
    assert target['missing_category'] == category
    assert target['missing_reason']
    assert target['value'] != 'N/A'


def test_observation_does_not_replace_saved_numeric_price_or_canonical_data():
    from report_preview import build_report_preview
    from recommendation_labels import normalize_recommendation_label
    assert normalize_recommendation_label('Neutral') == '持有'
    snapshot = {'rerun_context': {'parsed': {'trade_setup': {
        'trade_direction': 'Neutral', 'target_price': 'NT$150'}}}}
    result = build_report_preview('v4', '3017.TW', {}, snapshot=snapshot)
    assert result['targets'][1]['value'] == 'NT$150'
    assert 'missing_category' not in result['targets'][1]


def test_absent_direction_does_not_invent_an_observation_decision():
    from report_preview import build_report_preview
    result = build_report_preview('v4', '3017.TW', {})
    assert result['primary']['value'].startswith('尚未確認')
    assert result['targets'][1]['missing_category'] == 'unconfirmed'


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3'])
def test_other_mode_previews_explain_missing_targets_without_filling_them(mode):
    from report_preview import build_report_preview
    recommendation = {'recommendation': 'Neutral', 'target_3m': None, 'target_12m': 'N/A'}
    before = deepcopy(recommendation)
    preview = build_report_preview(mode, '3017.TW', recommendation)
    assert preview['primary']['value'] == '觀望'
    assert preview['targets'][-1]['missing_category'] == 'unconfirmed'
    assert preview['targets'][-1]['missing_reason']
    assert recommendation == before


def test_new_financial_originals_use_the_existing_separate_reference_boundary():
    from test_annual_filing_reference import reference
    from report_reader_assets import reader_observations
    snapshot = {'data': {'ticker': '2892.TW', 'financial_currency': 'TWD', 'free_cash_flow_raw': -99},
                '_reader_annual_cash_flow_review': {
                    'schema': 'official-annual-cash-flow-reference:v1', 'ticker': '2892.TW', 'year': 2025,
                    'annual_filing_reference': reference()}}
    before = deepcopy(snapshot)
    cash = reader_observations(snapshot)['evidence_gaps']['cash_flow']
    assert cash['status'] == 'unverified' and cash['raw_scalar'] == -99
    assert cash['annual_reference']['status'] == 'official_annual_cash_flow_verified'
    assert cash['annual_reference']['scope'] == 'consolidated'
    assert cash['annual_reference']['statement_taxonomy'] == 'financial_holding'
    assert cash['annual_reference']['five_year_history_verified'] is True
    assert cash['annual_reference']['industrial_dcf_applicable'] is False
    assert snapshot == before


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3'])
def test_preview_recovers_explicit_observation_after_canonical_history_normalization(mode):
    from report_index_parsing import parse_recommendation_summary
    from report_preview import build_report_preview
    markdown = '[投資建議]\n建議：Neutral\n[/投資建議]'
    recommendation = parse_recommendation_summary('3017_TW_'+mode+'_report_20261018_020035.html', markdown_text=markdown)
    assert recommendation['recommendation'] == '持有'
    original = deepcopy(recommendation)
    assert build_report_preview(mode, '3017.TW', recommendation, markdown_text=markdown)['primary']['value'] == '觀望'
    assert recommendation == original


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3'])
def test_standard_renderer_canonical_markdown_does_not_hide_the_original_observation(mode):
    from report_preview import build_report_preview
    from reporting.decision_context import build_decision_context
    from reporting.mode_templates import decision_markdown_heading, get_report_template_profile
    parsed = {'recommendation': {'建議': 'Neutral'}}
    decision = build_decision_context(parsed, pipeline_id=mode)
    assert decision['rec_text'] == '持有'
    heading = decision_markdown_heading(get_report_template_profile(mode))
    markdown = f'{heading}\n- **綜合建議:** {decision["rec_text"]}\n'
    snapshot = {'rerun_context': {'parsed': parsed}}
    result = build_report_preview(mode, '3017.TW', {'recommendation':'持有'}, markdown_text=markdown, snapshot=snapshot)
    assert result['primary']['value'] == '觀望'


def test_display_projection_does_not_undo_a_calibrated_holding_or_infer_from_market_neutrality():
    from report_preview import build_report_preview
    calibration = {'recommendation': '持有', 'recommendation_calibration': {'status': 'adjusted'}}
    snapshot = {'rerun_context': {'parsed': {'recommendation': {'建議': 'Neutral'}}}}
    assert build_report_preview('v1', '3017.TW', calibration, snapshot=snapshot)['primary']['value'] == '持有'
    assert build_report_preview('v1', '3017.TW', {'recommendation': '持有'}, markdown_text='市場情緒中性，暫無方向。')['primary']['value'] == '持有'


def test_non_swing_tracking_card_uses_the_same_display_projection_as_preview():
    html = javascript('''window.StockAgentHistoryPanelRenderers.create({
        escapeHtml: window.StockAgentUi.escapeHtml,
        normalizeRecommendation: window.StockAgentUi.normalizeRecommendation,
        recommendationTone: window.StockAgentUi.recommendationTone
    }).renderReportCard({ticker:'3017.TW', pipeline_id:'v1', filename:'sample.html',
        recommendation:{recommendation:'持有'}, decision_tracking:{status:'tracked',recommendation:'持有'},
        preview:{primary:{value:'觀望',tone:'is-neutral'}}},false)''')
    assert 'tracking-recommendation is-neutral">觀望<' in html
    assert '持有' not in html


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3'])
@pytest.mark.parametrize('rendered_markdown', [False, True])
def test_historical_api_projection_keeps_canonical_holding_but_displays_raw_observation(tmp_path, monkeypatch, mode, rendered_markdown):
    import report_index
    from report_history_service import list_reports
    monkeypatch.setattr(report_index, 'CACHE_DB_PATH', str(tmp_path/'index.sqlite3'))
    filename = '3017_TW_'+mode+'_report_20261018_020035.html'
    (tmp_path/filename).write_text('<html><body>保存報告</body></html>')
    markdown = '[投資建議]\n建議：Neutral\n[/投資建議]'
    if rendered_markdown:
        from reporting.decision_context import build_decision_context
        from reporting.mode_templates import decision_markdown_heading, get_report_template_profile
        heading = decision_markdown_heading(get_report_template_profile(mode))
        value = build_decision_context({'recommendation':{'建議':'Neutral'}}, pipeline_id=mode)['rec_text']
        markdown = f'{heading}\n- **綜合建議:** {value}\n'
    (tmp_path/filename.replace('.html','.md')).write_text(markdown)
    snapshot = json.dumps({'ticker':'3017.TW','pipeline':mode,
                           'rerun_context':{'parsed':{'recommendation':{'建議':'Neutral'}}},
                           'data':{'ticker':'3017.TW','current_price':100}})
    data_path = tmp_path/filename.replace('.html','.data.json')
    data_path.write_text(snapshot)
    report = list_reports(page=1, limit=20, q='3017', pipeline=mode, recommendation='all',
                          data_trust='all', output_dir=str(tmp_path), report_cache={}, include_versions=True)['reports'][0]
    assert report['recommendation']['recommendation'] == '持有'
    assert report['preview']['primary']['value'] == '觀望'
    assert data_path.read_text() == snapshot
    assert (tmp_path/filename.replace('.html','.md')).read_text() == markdown
