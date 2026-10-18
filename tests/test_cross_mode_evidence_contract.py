import copy
import json
from decimal import Decimal
import pytest

from evidence_exit_gate import evaluate_report_evidence
from final_output_completion import assess_final_completion
from structured_output_runtime import process_agent_response
from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
from report_publication_identity import publication_identity
from decision_tracking import build_decision_tracking
from reporting.target_price_text import target_price_text
from report_view_repair import repair_report_html_for_view, repair_report_markdown_for_download


def test_scenario_table_price_cannot_match_unrelated_short_sales_or_revenue():
    md = '| 情境 | 成長假設 | 成長率 | 合理股價 |\n|---|---|---|---|\n| 基本 | AI 成長 | 營收 CAGR 8.6% | NT$49.0 |'
    gate = evaluate_report_evidence(md, {'data': {'revenue': 49, 'chip_data': {'twse_margin_short_sales': {'short_balance': 49}}}})
    claim = next(c for c in gate['sampled_claims'] if c['reported_value'] == 49)
    assert claim['label'] == '合理股價'
    assert claim['status'] == 'unverifiable'
    assert claim['verification_reason_code'] == 'scenario_target_not_observed_fact'
    assert gate['verdict'] == 'caution'


def test_revenue_and_short_balance_same_number_keep_distinct_semantics():
    snapshot = {'data': {'revenue': 48, 'chip_data': {'twse_margin_short_sales': {'short_balance': 49}}}}
    gate = evaluate_report_evidence('營收: 49\n融券餘額: 49', snapshot)
    assert [c['status'] for c in gate['sampled_claims']] == ['mismatch', 'verified']
    assert gate['sampled_claims'][0]['matched_path'] == 'data.revenue'


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_arithmetic_and_annual_ttm_mismatch_rejected_in_all_modes(mode):
    snapshot = {'pipeline': mode, 'data': {'current_price': 29.9, 'trailing_eps': 1.11}}
    before = copy.deepcopy(snapshot)
    md = '以 2025 年 EPS 1.35 元與當前股價 29.9 元計算，TTM P/E 為 26.94x。'
    gate = evaluate_report_evidence(md, snapshot)
    assert gate['verdict'] == 'rejected'
    claim = next(c for c in gate['sampled_claims'] if c['claim_type'] == 'derived_calculation')
    assert claim['calculated_value'] == pytest.approx(22.148148)
    assert 'annual_eps_used_for_ttm_pe' in claim['issues']
    with pytest.raises(ReportPublicationBlockedError):
        assert_report_publishable({'evidence_exit_gate': gate})
    assert snapshot == before


@pytest.mark.parametrize('text', [
    '以 TTM EPS 1.11 元與當前股價 29.9 元計算，TTM P/E 為 26.94x。',
    '以 2025 年 EPS 1.35 元與當前股價 29.9 元計算，P/E 為 22.15x。',
])
def test_valid_period_and_arithmetic_remain_usable(text):
    gate = evaluate_report_evidence(text, {'data': {'current_price': 29.9, 'trailing_eps': 1.11, 'currency': 'TWD', 'financial_currency': 'TWD'}})
    assert gate['failed_count'] == 0
    assert any(c['claim_type'] == 'derived_calculation' and c['status'] == 'verified' for c in gate['sampled_claims'])


@pytest.mark.parametrize('role', [7, 16, 19, 24])
@pytest.mark.parametrize('reason', ['MAX_TOKENS', 'LENGTH', 'SAFETY', 'RECITATION'])
def test_known_incomplete_final_is_partial_non_prediction_and_not_publishable(role, reason):
    raw = final_payload(role)
    context = {'pipeline_id': {7: 'v1', 16: 'v2', 19: 'v3', 24: 'v4'}[role], 'data': {}}
    result = process_agent_response(role, json.dumps(raw), context, completion_diagnostics={'finish_reasons': [reason]})
    from memo_output_completion import incomplete_memo_roles
    assert any(r['agent'] == role for r in incomplete_memo_roles(context))
    assert 'recommendation' not in context['structured_outputs'].get(role, {})
    from agent_runtime.quality_structured_outputs import try_parse_structured_output
    try_parse_structured_output(role, result, context)
    assert publication_identity(context)['kind'] == 'partial_analysis'
    assert not publication_identity(context)['prediction_eligible']
    assert build_decision_tracking({}, snapshot=context)['status'] == 'excluded_incomplete'
    with pytest.raises(ReportPublicationBlockedError): assert_report_publishable(context)


def final_payload(role):
    return {'recommendation': {'建議': '避免'}, 'confidence_basis': {'summary': '證據有限'},
            'scenario_triggers': [{'trigger_condition': '需重新查核', 'action': '重評'}],
            'analysis_markdown': '保留研究限制，資料不足時不新增部位。',
            'position_plan' if role == 16 else 'short_setup': {'action': '等待'}}


@pytest.mark.parametrize('role', [16, 19])
def test_complete_raw_contract_and_missing_fields_do_not_use_defaults(role):
    raw = final_payload(role)
    assert assess_final_completion(role, json.dumps(raw), {'finish_reasons': ['STOP']})['status'] == 'complete'
    assert assess_final_completion(role, json.dumps(raw)[:-1], {'finish_reasons': ['STOP']})['status'] == 'incomplete'
    raw.pop('confidence_basis')
    assert assess_final_completion(role, json.dumps(raw), {'finish_reasons': ['STOP']})['status'] == 'incomplete'


@pytest.mark.parametrize('value', [0, -1, 0.0, 'NT$0', '-2', Decimal('0'), Decimal('-3')])
def test_non_positive_scenario_prices_are_unavailable(value):
    assert target_price_text(value) == 'N/A'


def test_view_only_zero_repair_preserves_legitimate_zero_and_original():
    html = '<div>基本情境估值</div><div>NT$0</div><p>自由現金流 NT$0</p>'
    fixed = repair_report_html_for_view(html)
    assert 'N/A（原估值輸出不可用）' in fixed
    assert '自由現金流 NT$0' in fixed
    assert '基本情境估值</div><div>NT$0' in html
    assert 'N/A（原估值輸出不可用）' in repair_report_markdown_for_download('基本情境: NT$0\n自由現金流: NT$0')


def test_mixed_currency_arithmetic_cannot_be_verified():
    gate = evaluate_report_evidence('以 TTM EPS 1.11 與當前股價 29.9 計算，TTM P/E 為 26.94x。',
        {'data': {'trailing_eps': 1.11, 'currency': 'TWD', 'financial_currency': 'USD'}})
    assert gate['verdict'] == 'rejected'
    assert 'price_eps_currency_mismatch' in gate['sampled_claims'][0]['issues']


def test_clarified_annual_and_ttm_eps_do_not_use_the_wrong_denominator():
    gate = evaluate_report_evidence('2025 年 EPS 1.35 元，TTM EPS 1.11 元與當前股價 29.9 元計算，TTM P/E 為 26.94x。',
        {'data': {'trailing_eps': 1.11, 'currency': 'TWD', 'financial_currency': 'TWD'}})
    assert gate['failed_count'] == 0
    claim = next(c for c in gate['sampled_claims'] if c['claim_type'] == 'derived_calculation')
    assert claim['arithmetic_inputs']['eps_per_share'] == 1.11


def test_future_cards_reject_zero_targets_without_claiming_minus_100_percent():
    from reporting.summary_cards import build_price_target_cards_html
    html = build_price_target_cards_html({'基本情境': 0, '牛市情境': 49}, 42)
    assert 'NT$0' not in html and '-100' not in html
    assert 'NT$49' in html


@pytest.mark.parametrize('role', [16, 19])
def test_partial_final_cache_is_not_read_or_written(role, monkeypatch):
    from agent_runtime import step_cache
    writes = []
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_SECONDS', 100)
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda *a, **k: writes.append(a))
    incomplete = assess_final_completion(role, json.dumps(final_payload(role)), {'finish_reasons': ['MAX_TOKENS']})
    context = {'structured_outputs': {role: {'output_completion': incomplete}}}
    step_cache.store_cached_agent_step('key', agent_num=role, context=context, model_id='test', text='partial')
    assert not writes
    monkeypatch.setattr(step_cache, 'candidate_cache_read_allowed', lambda *a: True)
    monkeypatch.setattr(step_cache, 'get_cache_json', lambda *a: {'agent_num': role, 'text': 'draft', 'structured_output': {}})
    assert step_cache.get_cached_agent_step('key') is None


@pytest.mark.parametrize('role', [16, 19])
def test_same_response_reparse_cannot_erase_finish_receipt_and_real_stop_can_override(role):
    raw = json.dumps(final_payload(role))
    first = assess_final_completion(role, raw, {'finish_reasons': ['MAX_TOKENS']})
    assert assess_final_completion(role, raw, None, first)['status'] == 'incomplete'
    assert assess_final_completion(role, raw, {'finish_reasons': ['STOP']}, first)['status'] == 'complete'
    ctx = {'data': {}}
    process_agent_response(role, raw, ctx, completion_diagnostics={'finish_reasons': ['MAX_TOKENS']})
    process_agent_response(role, raw, ctx)
    assert ctx['structured_outputs'][role]['output_completion']['status'] == 'incomplete'


def test_legacy_views_without_ledger_get_current_trace_without_mutating_input():
    from reporting.reading_notice import build_report_reading_notice_html
    context = {'_current_quality_projection': True, 'evidence_exit_gate': {'verdict': 'caution', 'sampled_claims': [
        {'label': '合理股價', 'reported_value': 49, 'status': 'unverifiable', 'verification_reason_code': 'scenario_target_not_observed_fact'}]}}
    original = '<html><body>' + build_report_reading_notice_html(context) + '<p>歷史原文</p></body></html>'
    fixed = repair_report_html_for_view(original, context)
    assert '情境推估，非觀測事實' in fixed and fixed.count('class="evidence-ledger"') == 1
    assert 'class="evidence-ledger"' not in original
    twice = repair_report_html_for_view(fixed, context)
    assert twice.count('class="evidence-ledger"') == 1
    md = repair_report_markdown_for_download('歷史原文', context)
    assert '情境推估，非觀測事實' in md and md.count('<!-- evidence-ledger:start -->') == 1
