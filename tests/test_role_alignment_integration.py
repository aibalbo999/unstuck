import json
from datetime import date, timedelta

import pytest


@pytest.mark.parametrize('agent', [15, 16])
def test_mode_b_receives_real_daily_technical_evidence_in_prompt_and_state(agent):
    from agent_runtime.prompting import build_prompt
    from state_memory import initialize_agent_state, state_view_for
    today = date.today()
    bars = [{'date': (today - timedelta(days=80-i)).isoformat(), 'open': 100+i,
             'high': 103+i, 'low': 98+i, 'close': 102+i, 'volume': 1000+i} for i in range(80)]
    data = {'ticker': 'TEST.TW', 'company_name': '測試公司', 'current_price': 181,
            'daily_market_data': {'bars': bars, 'source': 'fixture-daily', 'volume_unit': 'shares'}}
    state = initialize_agent_state(data)
    view = state_view_for(agent, state)
    assert view['short_term_market_context']['technical_indicators']['atr_14'] is not None
    prompt = build_prompt(agent, data, {'pipeline_id': 'v2', 'agent_state': state})
    payload = json.loads(prompt.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])
    assert payload['short_term_market_context']['daily_market_data']['source'] == 'fixture-daily'
    assert payload['short_term_market_context']['daily_market_data']['volume_unit'] == 'shares'
    assert payload['short_term_market_context']['technical_indicators']['atr_14'] is not None


@pytest.mark.parametrize('agent', [3, 12])
def test_moat_trend_is_preserved_separately_from_evidence_scores(agent):
    from structured_outputs import normalize_structured_output, structured_output_to_report_text
    raw = {'reasoning_steps': ['來源有限', '部分查核', '保留缺口'], 'moat_scores': {},
           'moat_trend': 'unassessed', 'moat_trend_reason': '只有單期資料，無法判定擴張或收縮',
           'analysis_markdown': '本次僅能確認現況。'}
    out = normalize_structured_output(agent, raw)
    assert out['moat_trend'] == 'unassessed'
    assert all(v is None for v in out['moat_scores'].values())
    assert '只有單期資料' in structured_output_to_report_text(agent, out)
    assert '護城河趨勢' not in out['moat_scores']


def _reconciliation(status='aligned'):
    return {'status': status, 'pending_recalculation': status == 'conflict', 'checks': [
        {'topic': topic, 'status': status, 'valuation_quote': '成長假設10%',
         'growth_quote': '可支持10%成長', 'rationale': '兩者同一期間且有來源'}
        for topic in ('baseline', 'period', 'growth', 'capex_margin', 'calculation')]}


def test_reconciliation_checks_real_upstream_quotes_and_pending_recalculation():
    from research_assumption_contract import assess_reconciliation
    context = {'analyses': {4: '基本情境成長假設10%', 5: '已驗證產能可支持10%成長'}}
    good = _reconciliation()
    assert assess_reconciliation(good, context)['issues'] == []
    good['checks'][0]['valuation_quote'] = '不存在的計算已驗證'
    assert 'unsupported_valuation_quote' in assess_reconciliation(good, context)['issues']
    conflict = _reconciliation('conflict')
    conflict['pending_recalculation'] = False
    assert 'conflict_requires_recalculation' in assess_reconciliation(conflict, context)['issues']


def test_reconciliation_unknown_does_not_default_to_agreement_or_fake_sources():
    from research_assumption_contract import assess_reconciliation
    assert assess_reconciliation(None, {})['issues']
    unknown = _reconciliation('unassessed')
    for row in unknown['checks']:
        row.update(valuation_quote='', growth_quote='', rationale='缺少對應期間來源，未評估')
    result = assess_reconciliation(unknown, {})
    assert result['issues'] == [] and result['status'] == 'unassessed'
    unknown['status'] = 'aligned'
    assert 'inconsistent_reconciliation_status' in assess_reconciliation(unknown, {})['issues']


def test_revoked_sizing_inputs_do_not_become_available_and_wait_does_not_hide_an_order():
    from position_sizing import build_position_sizing_context
    from position_sizing_runtime import trusted_sizing_context, assess_position_plan
    known = build_position_sizing_context({'capital_amount': 100000, 'risk_budget_amount': 1000,
        'currency': 'TWD', 'scenario_type': 'research', 'position_state': 'no_position',
        'existing_position_percent': 0}, source_ref='request:test', quote_currency='TWD')
    assert known['status'] == 'available'
    known['status'] = 'unavailable'
    assert trusted_sizing_context({'position_sizing_context': known})['status'] == 'unavailable'
    plan = {'action': '等待', 'position_size': '0%', 'invalidation_condition': '等待財報後重新評估'}
    assert assess_position_plan(plan, {}, '買入', '研究評價買入，但不應立即進場。')['issues'] == []
    assert assess_position_plan(plan, {}, '買入', '請立即買入建立部位。')['issues']


def test_raw_wait_size_contradiction_remains_blocked_after_normalization():
    from structured_output_runtime import process_agent_response
    from agent_runtime.structured_repair_contracts import structured_output_missing
    payload = {'recommendation': {'建議': '買入'}, 'analysis_markdown': '研究估值有上行，等待風險預算。',
               'position_plan': {'action': '等待', 'position_size': '100%',
                                 'invalidation_condition': '等待財報後重新評估'}}
    context = {'pipeline_id': 'v2', 'structured_outputs': {}, 'data': {}}
    process_agent_response(16, json.dumps(payload), context)
    assert context['structured_outputs'][16]['position_plan']['position_size'] == '0%'
    assert context['structured_outputs'][16]['position_sizing_assessment']['issues']
    assert structured_output_missing(context, 16)


@pytest.mark.parametrize('body', ['後續營收值得期待，請立即買入建立部位。', '不必等待，請立即買入建立部位。', '請立即續抱現有20%部位。'])
def test_waiting_plan_rejects_immediate_orders_despite_incidental_wait_words(body):
    from position_sizing_runtime import assess_position_plan
    plan = {'action': '等待', 'position_size': '0%', 'invalidation_condition': '等待財報後重新評估'}
    assert assess_position_plan(plan, {}, '買入', body)['issues']


@pytest.mark.parametrize('body', ['若財報改善，請立即買入。', '待風險預算確認後再立即進場。', '不應立即買入。'])
def test_waiting_plan_keeps_explicit_conditions_and_prohibitions(body):
    from position_sizing_narrative import waiting_plan_has_immediate_order
    assert not waiting_plan_has_immediate_order(body)


def test_reconciliation_cannot_quote_empty_containers_or_metadata_keys():
    from research_assumption_contract import assess_reconciliation
    for quote in ('{}', 'analysis_markdown'):
        value = _reconciliation()
        for row in value['checks']:
            row.update(valuation_quote=quote, growth_quote=quote)
        context = {'structured_outputs': {4: {'analysis_markdown': ''}, 5: {'analysis_markdown': ''}}}
        assert assess_reconciliation(value, context)['issues']


@pytest.mark.parametrize('action', [{}, [], {'value': '等待'}, None])
def test_raw_malformed_action_returns_blocked_receipt_instead_of_crashing(action):
    from position_sizing_runtime import assess_position_plan
    result = assess_position_plan({'action': action, 'position_size': '0%'}, {}, '買入')
    assert result['status'] == 'blocked' and result['issues']


def test_explicit_sizing_context_survives_workflow_json_round_trip():
    from types import SimpleNamespace
    from workflow_context import graph_delta_from_legacy_context, legacy_context_from_graph
    from position_sizing import build_position_sizing_context
    from position_sizing_runtime import trusted_sizing_context
    sizing = build_position_sizing_context({'capital_amount': 100000, 'risk_budget_amount': 1000,
        'currency': 'TWD', 'scenario_type': 'research', 'position_state': 'no_position',
        'existing_position_percent': 0}, source_ref='request:scenario', quote_currency='TWD')
    context = {'pipeline_id': 'v2', 'position_sizing_context': sizing}
    delta = json.loads(json.dumps(graph_delta_from_legacy_context(context)))
    restored = legacy_context_from_graph({'pipeline_id': 'v2', 'run_id': 'sizing-test', 'ticker': 'TEST.TW', 'company_name': '測試公司', **delta}, SimpleNamespace(progress_callback=None, cancel_check=None))
    assert trusted_sizing_context(restored) == sizing
    restored['position_sizing_context']['inputs']['capital_amount'] = 1
    assert sizing['inputs']['capital_amount'] == 100000
    assert trusted_sizing_context(restored)['status'] == 'unavailable'


@pytest.mark.parametrize('invalid', [False, True])
def test_reconciliation_receipt_reaches_runtime_repair_and_final_audit(invalid):
    from structured_output_runtime import process_agent_response
    from structured_output_parser import parse_structured_data
    from agent_runtime.structured_repair_contracts import structured_output_missing
    from final_audit import run_final_report_audit
    value = _reconciliation('unassessed')
    for row in value['checks']:
        row.update(valuation_quote='', growth_quote='', rationale='缺乏同期間資料，未評估')
    if invalid:
        value['checks'][0].update(status='aligned', valuation_quote='{}', growth_quote='{}')
    payload = {'recommendation': {'建議': '持有'}, 'assumption_reconciliation': value,
               'analysis_markdown': '暫列研究清單；缺乏假設對照資料，尚未重算目標價。'}
    context = {'pipeline_id': 'v1', 'agent_sequence': [7], 'data': {}, 'analyses': {}, 'structured_outputs': {}}
    context['analyses'][7] = process_agent_response(7, json.dumps(payload, ensure_ascii=False), context)
    assert structured_output_missing(context, 7) is invalid
    context['parsed'] = parse_structured_data(context)
    audit = run_final_report_audit(context, append_section=False)
    errors = [v for v in audit.get('critical', []) if '成長與估值假設對照' in v]
    assert bool(errors) is invalid
    assert '成長與估值假設對照' in context['analyses'][7]


@pytest.mark.parametrize('fenced', [False, True])
def test_trade_plan_without_markdown_does_not_append_raw_json(fenced):
    from test_trade_catalyst_semantics import separated_case
    from structured_output_runtime import process_agent_response
    from trade_financial_risk import NEGATIVE_FCF_WARNING
    payload, context = separated_case()
    payload.pop('analysis_markdown', None)
    raw = json.dumps(payload, ensure_ascii=False)
    text = process_agent_response(24, '```json\n' + raw + '\n```' if fenced else raw, context)
    assert '"core_catalyst"' not in text
    assert text.count(NEGATIVE_FCF_WARNING) == 1
    assert payload['observed_signal'] in text
