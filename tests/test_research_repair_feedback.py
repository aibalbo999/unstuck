"""Actionable A7 repair feedback without changing evidence or model decisions."""
import copy
import json

import pytest

from agent_runtime.repair_state import repair_contract_issues
from research_assumption_contract import TOPICS
from structured_output_runtime import process_agent_response


VALUATION = '基本情境依當前價格與 TTM EPS 評估。牛市情境須觀察產能轉換，帶動未來兩年復甦。'
GROWTH = '毛利率有望自低點（24.1%，來源：data.history.rows）逐步回穩。'


def candidate():
    return {
        'recommendation': {'建議': '持有', '長期目標（12個月）': 'NT$110'},
        'analysis_markdown': '研究結論仍須更多證據確認。',
        'assumption_reconciliation': {
            'status': 'unassessed', 'pending_recalculation': False,
            'checks': [{'topic': topic, 'status': 'unassessed', 'valuation_quote': '',
                       'growth_quote': '', 'rationale': '缺乏對應證據。'} for topic in TOPICS],
        },
    }


def decode(value):
    context = {'pipeline_id': 'v1', 'data': {'current_price': 100},
               'analyses': {4: VALUATION, 5: GROWTH}, 'structured_outputs': {}}
    context['analyses'][7] = process_agent_response(7, json.dumps(value, ensure_ascii=False), context,
                           completion_diagnostics={'finish_reasons': ['STOP']})
    return context


def feedback(context):
    before = copy.deepcopy(context)
    result = repair_contract_issues(7, context)
    assert context == before  # Diagnostics cannot rewrite quotes, labels or targets.
    return '\n'.join(result)


@pytest.mark.parametrize('status', ['aligned', 'conflict'])
def test_empty_quote_reports_field_source_and_actual_row_status(status):
    value = candidate()
    row = value['assumption_reconciliation']['checks'][3]
    row.update(status=status, valuation_quote='基本情境依當前價格與 TTM EPS 評估。')
    if status == 'conflict':
        value['assumption_reconciliation'].update(status='conflict', pending_recalculation=True)
    text = feedback(decode(value))
    assert 'capex_margin.growth_quote' in text and 'Agent 5' in text
    assert f'目前 status={status}' in text
    assert '引文為空' in text
    assert '無對應證據' in text and '本列標 unassessed' in text
    assert '連續逐字片段' not in text  # Empty evidence is not an altered quotation.


@pytest.mark.parametrize('field,source,quote', [
    ('valuation_quote', 4, '牛市情境...帶動未來兩年復甦'),
    ('growth_quote', 5, '毛利率有望自低點（24.1%）逐步回穩。'),
])
def test_nonverbatim_quote_is_distinct_from_missing_evidence(field, source, quote):
    value = candidate()
    value['assumption_reconciliation']['checks'][1][field] = quote
    text = feedback(decode(value))
    assert f'period.{field}' in text and f'Agent {source}' in text
    assert '目前 status=unassessed' in text
    assert '不是對應來源中的連續逐字片段' in text
    assert '不可省略、拼接或補造' in text
    assert '引文為空' not in text
    assert quote not in text  # Do not repeat erroneous source-like material.


def test_aggregate_mismatch_explains_expected_status_without_rewriting_it():
    value = candidate()
    value['assumption_reconciliation']['status'] = 'aligned'
    context = decode(value)
    text = feedback(context)
    assert 'assumption_reconciliation.status=aligned' in text
    assert '依目前五列應為 unassessed' in text
    assert context['structured_outputs'][7]['assumption_reconciliation']['status'] == 'aligned'


def test_conflict_requires_pending_recalculation_but_does_not_force_a_status_change():
    value = candidate()
    value['assumption_reconciliation']['status'] = 'conflict'
    row = value['assumption_reconciliation']['checks'][0]
    row.update(status='conflict', valuation_quote=VALUATION, growth_quote=GROWTH)
    text = feedback(decode(value))
    assert 'pending_recalculation=false' in text
    assert '保留 conflict 時必須為 true' in text
    assert '既有價格不代表已完成重算' in text


def test_feedback_requires_a_complete_rewrite_and_keeps_source_catalog_out():
    value = candidate()
    for row in value['assumption_reconciliation']['checks']:
        row.update(valuation_quote='被改寫的估值原文', growth_quote='被改寫的成長原文')
    context = decode(value)
    context['analyses'][4] += '巨量來源內容' * 5000
    text = feedback(context)
    assert '重寫完整候選' in text
    assert '正文、推薦與市場評估' in text
    assert '巨量來源內容' not in text
    assert len(text) < 1500  # Ten offending fields, not the large source catalog.
    assert len(repair_contract_issues(7, context)) <= 16  # Existing retry issue budget.


def test_valid_unassessed_and_verified_quotes_need_no_repair():
    value = candidate()
    value['assumption_reconciliation']['checks'][0]['valuation_quote'] = VALUATION
    assert feedback(decode(value)) == ''


@pytest.mark.parametrize('agent,pipeline', [(16, 'v2'), (19, 'v3'), (24, 'v4')])
def test_other_modes_keep_existing_missing_output_feedback(agent, pipeline):
    context = {'pipeline_id': pipeline, 'data': {'current_price': 100},
               'analyses': {}, 'structured_outputs': {}}
    issues = repair_contract_issues(agent, context)
    assert f'Agent {agent} 結構化輸出未通過本模式契約檢查。' in issues
    assert not any('假設對照' in item or 'assumption_reconciliation' in item for item in issues)


@pytest.mark.parametrize('quote', ['', '  \n\t'])
def test_first_rewrite_receives_current_field_diagnostic_from_generic_audit(quote):
    from agent_runtime.repair_reflection import build_audit_retry_instruction
    value = candidate()
    value['assumption_reconciliation']['checks'][3].update(
        status='conflict', valuation_quote=VALUATION, growth_quote=quote)
    context = decode(value)
    instruction = build_audit_retry_instruction(7, ['unsupported_growth_quote'],
        context=context, data=context['data'], previous_text=context['analyses'][7])
    assert 'capex_margin.growth_quote' in instruction
    assert '目前 status=conflict' in instruction and '引文為空' in instruction
    assert '重寫完整候選' in instruction


@pytest.mark.parametrize('mutation', ['schema', 'duplicate_topic', 'rationale'])
def test_malformed_reconciliation_stays_rejected(mutation):
    value = candidate()
    if mutation == 'schema':
        value['assumption_reconciliation'].pop('pending_recalculation')
    elif mutation == 'duplicate_topic':
        value['assumption_reconciliation']['checks'][0]['topic'] = 'period'
    else:
        value['assumption_reconciliation']['checks'][0]['rationale'] = '   '
    context = decode(value)
    assert repair_contract_issues(7, context)
    assert context['structured_outputs'][7]['assumption_reconciliation_assessment']['issues']


def test_bounded_loop_delivers_current_candidate_feedback_on_both_attempts(monkeypatch):
    import asyncio
    from agent_runtime import repair_loop
    initial = candidate()
    initial['assumption_reconciliation']['checks'][3].update(
        status='conflict', valuation_quote=VALUATION)
    context = decode(initial)
    current = candidate()
    current['assumption_reconciliation']['checks'][1]['valuation_quote'] = '牛市情境...帶動未來兩年復甦'
    values = [current, candidate()]
    instructions = []
    async def run(agent, data, context, rotator, **kwargs):
        instructions.append(context['_audit_retry_instruction'])
        return process_agent_response(7, json.dumps(values[len(instructions)-1], ensure_ascii=False),
            context, completion_diagnostics={'finish_reasons': ['STOP']})
    async def reflect(*args, **kwargs):
        return '僅修正現有證據與欄位矛盾。'
    monkeypatch.setattr(repair_loop, 'run_single_agent_async', run)
    monkeypatch.setattr(repair_loop, 'generate_audit_reflection_async', reflect)
    monkeypatch.setattr(repair_loop, 'repair_429_circuit_state', lambda *args: {})
    monkeypatch.setattr(repair_loop, 'get_audit_rewrite_model_sequence', lambda *args: ['offline'])
    result = asyncio.run(repair_loop._repair_agent_output_async(
        7, context['data'], context, None, ['unsupported_growth_quote']))
    assert result[0] and len(instructions) == 2
    blocks = [text.split('【本次 A7 假設對照診斷】\n', 1)[1].split('\n\n', 1)[0] for text in instructions]
    assert 'capex_margin.growth_quote' in blocks[0] and '引文為空' in blocks[0]
    assert 'period.valuation_quote' in blocks[1] and '不是對應來源中的連續逐字片段' in blocks[1]
    assert 'capex_margin.growth_quote' not in blocks[1]  # Historical checklist is separate.
    assert not context['structured_outputs'][7]['assumption_reconciliation_assessment']['issues']


def test_combined_feedback_fits_existing_sixteen_issue_budget():
    value = candidate()
    value['assumption_reconciliation']['status'] = 'aligned'
    for row in value['assumption_reconciliation']['checks']:
        row.update(status='conflict', valuation_quote='不符原文', growth_quote='不符原文', rationale=' ')
    context = decode(value)
    issues = repair_contract_issues(7, context)
    assert len(issues) <= 16
    assert '重寫完整候選' in '\n'.join(issues[:16])
