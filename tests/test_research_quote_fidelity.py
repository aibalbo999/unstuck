"""Restore only provable source formatting; never repair missing evidence."""
import copy
import hashlib
import json

import pytest

from research_assumption_contract import TOPICS, assess_reconciliation
from structured_output_runtime import process_agent_response


SOURCE = '**基本情境（948.0 TWD）**：對應 46.09x 本益比。'
QUOTE = '基本情境（948.0 TWD）：對應 46.09x 本益比。'


def candidate(quote=QUOTE):
    return {'recommendation': {'建議': '持有', '長期目標（12個月）': 'NT$110'},
        'analysis_markdown': '研究結論待更多證據確認。',
        'assumption_reconciliation': {'status': 'unassessed', 'pending_recalculation': False,
            'checks': [{'topic': topic, 'status': 'unassessed', 'valuation_quote': quote if index == 0 else '',
                'growth_quote': '', 'rationale': '成長資料不足，無法確認假設。'} for index, topic in enumerate(TOPICS)]}}


def run(payload, sources=None):
    context = {'pipeline_id': 'v1', 'data': {'current_price': 100},
        'analyses': sources or {4: SOURCE, 5: '成長來源不足'}, 'structured_outputs': {}}
    raw = json.dumps(payload, ensure_ascii=False)
    text = process_agent_response(7, raw, context)
    return context, context['structured_outputs'][7], text, raw


def test_runtime_restores_unique_contiguous_current_source_and_records_exact_evidence():
    payload = candidate(); before = copy.deepcopy(payload)
    context, output, text, raw = run(payload)
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == SOURCE
    assert SOURCE in text
    assert assess_reconciliation(output['assumption_reconciliation'], context)['issues'] == []
    receipt = output['assumption_quote_restoration']
    assert receipt['raw_response_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    item = receipt['changes'][0]
    assert (item['topic'], item['field'], item['source_agent']) == ('baseline', 'valuation_quote', 4)
    witness = item['sources'][0]
    assert witness['source_sha256'] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert SOURCE[witness['start']:witness['end']] == SOURCE
    assert output['recommendation']['建議'] == '持有'
    assert output['assumption_reconciliation']['status'] == 'unassessed'
    assert payload == before
    assert receipt['upstream_fingerprint'] == output['assumption_reconciliation_assessment']['upstream_fingerprint']


@pytest.mark.parametrize('quote', [
    QUOTE.replace('948.0', '949.0'), QUOTE.replace('對應 ', '對應'),
    QUOTE.replace('本益比', '市盈率'), QUOTE.replace('：', ':'),
    QUOTE.replace('（948.0 TWD）', ''), '基本情境...46.09x 本益比。',
])
def test_nonformatting_changes_stay_rejected(quote):
    context, output, _, _ = run(candidate(quote))
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == quote
    assert 'unsupported_valuation_quote' in assess_reconciliation(output['assumption_reconciliation'], context)['issues']
    assert 'assumption_quote_restoration' not in output


@pytest.mark.parametrize('source', [r'\**成長10%\**', '***成長10%***', '```**成長10%**```', '**成長10%', '`**成長10%**`'])
def test_unsupported_markup_cannot_be_reinterpreted(source):
    context, output, _, _ = run(candidate('成長10%'), {4: source})
    # An already exact substring stays unchanged and never acquires a restoration receipt.
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == '成長10%'
    assert 'assumption_quote_restoration' not in output


def test_different_reconstructed_literals_are_ambiguous_but_duplicate_evidence_is_not():
    payload = candidate('本次成長10%可驗證')
    context, output, _, _ = run(payload, {4: '本次**成長10%**可驗證', 5: 'irrelevant'})
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == '本次**成長10%**可驗證'
    context = {'pipeline_id': 'v1', 'analyses': {4: '本次**成長10%**可驗證'},
        'structured_outputs': {4: {'analysis_markdown': '本次**成長10%可驗證**'}}}
    process_agent_response(7, json.dumps(payload, ensure_ascii=False), context)
    output = context['structured_outputs'][7]
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == '本次成長10%可驗證'
    assert output['assumption_reconciliation_assessment']['issues']


def test_receipt_lists_identical_literal_in_distinct_current_source_values():
    context = {'pipeline_id': 'v1', 'analyses': {4: SOURCE},
        'structured_outputs': {4: {'analysis_markdown': '研究原文：' + SOURCE}}}
    process_agent_response(7, json.dumps(candidate(), ensure_ascii=False), context)
    item = context['structured_outputs'][7]['assumption_quote_restoration']['changes'][0]
    assert len(item['sources']) == 2


def test_cross_role_and_cross_leaf_sources_cannot_supply_missing_quote():
    for context in ({'analyses': {4: 'unrelated', 5: SOURCE}},
                    {'structured_outputs': {4: {'left': '**基本情境（948.0 TWD）**', 'right': '：對應 46.09x 本益比。'}}}):
        process_agent_response(7, json.dumps(candidate(), ensure_ascii=False), context)
        output = context['structured_outputs'][7]
        assert output['assumption_reconciliation_assessment']['issues']
        assert 'assumption_quote_restoration' not in output


def test_forged_receipt_never_survives_provider_ingress_and_snapshot_receipt_is_preserved():
    from structured_output_normalizer import normalize_structured_output
    payload = candidate(SOURCE);payload['assumption_quote_restoration'] = {'forged': True}
    _, output, _, _ = run(payload)
    assert 'assumption_quote_restoration' not in output
    _, restored, _, _ = run(candidate())
    assert normalize_structured_output(7, restored)['assumption_quote_restoration'] == restored['assumption_quote_restoration']
    # A historical conversion record cannot authorize a new response with changed upstream.
    context, output, _, _ = run(restored, {4: '來源已更正，舊目標失效'})
    assert 'assumption_quote_restoration' not in output
    assert output['assumption_reconciliation_assessment']['issues']


def test_repair_feedback_names_each_unsupported_field_without_weakening_the_gate():
    from agent_runtime.repair_state import repair_contract_issues
    context, output, _, _ = run(candidate(QUOTE.replace('（948.0 TWD）', '')))
    feedback = repair_contract_issues(7, context)
    assert any('baseline.valuation_quote' in issue and 'Agent 4' in issue for issue in feedback)
    assert 'unsupported_valuation_quote' in output['assumption_reconciliation_assessment']['issues']


@pytest.mark.parametrize('source,quote', [
    ('**本次成長**支持**持續增加**', '成長支持持續'),
    (r'前文\**成長10%\**後文', '前文成長10%後文'),
    ('前文***成長10%***後文', '前文成長10%後文'),
    ('```\n前文**成長10%**後文\n```', '前文成長10%後文'),
    ('前文`**成長10%**`後文', '前文成長10%後文'),
    ('前文**成長10%後文', '前文成長10%後文'),
    ('2**3+4**5', '23+45'),
    (r'**EPS 10\** 元', r'EPS 10\ 元'),
    ('~~~\n前文**成長10%**後文\n~~~', '前文成長10%後文'),
    ('    前文**成長10%**後文', '前文成長10%後文'),
    ('\t前文**成長10%**後文', '前文成長10%後文'),
    ('````\n```\n前文**成長10%**後文\n````', '前文成長10%後文'),
])
def test_partial_bold_or_nonbold_syntax_is_not_a_restoration_witness(source, quote):
    _, output, _, _ = run(candidate(quote), {4: source})
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == quote
    assert output['assumption_reconciliation_assessment']['issues']
    assert 'assumption_quote_restoration' not in output


def test_invalid_response_cannot_retain_a_previous_conversion_receipt():
    context, output, _, _ = run(candidate())
    process_agent_response(7, 'not valid JSON', context)
    assert 7 not in context['structured_outputs']


def test_other_roles_cannot_publish_model_supplied_research_restoration_receipts():
    from test_short_observation_fidelity import _research_setup
    payload = {'recommendation': {'建議': '避免'}, 'short_setup': _research_setup(),
        'analysis_markdown': '本研究情境不建立空方部位。',
        'assumption_quote_restoration': {'policy': 'forged', 'changes': [{'forged': True}]}}
    context = {'pipeline_id': 'v3'}
    process_agent_response(19, json.dumps(payload, ensure_ascii=False), context)
    assert 'assumption_quote_restoration' not in context['structured_outputs'][19]


def test_repeated_partial_matches_hit_the_bound_without_searching_for_a_later_repair():
    source = ('**ABCDE** x **FGHIJ**; ' * 65) + '**CDE** x **FGH**'
    _, output, _, _ = run(candidate('CDE x FGH'), {4: source})
    assert 'assumption_quote_restoration' not in output
    assert output['assumption_reconciliation_assessment']['issues']


def test_source_format_recovery_does_not_waive_conflict_recalculation_or_price_direction():
    from agent_runtime.repair_state import repair_contract_issues
    payload = candidate()
    payload['assumption_reconciliation'].update(status='conflict', pending_recalculation=False)
    payload['assumption_reconciliation']['checks'][0]['status'] = 'conflict'
    payload['recommendation']['長期目標（12個月）'] = 'NT$150'
    context, output, _, _ = run(payload)
    assert output['assumption_reconciliation']['checks'][0]['valuation_quote'] == SOURCE
    assert 'conflict_requires_recalculation' in output['assumption_reconciliation_assessment']['issues']
    assert any('建議/報酬矛盾' in item for item in repair_contract_issues(7, context))


@pytest.mark.parametrize('agent', [7, 19])
def test_changed_evidence_contract_does_not_reuse_pre_fidelity_normalized_cache(agent, monkeypatch):
    from agent_runtime import step_cache
    from test_agent_step_output_contract import _inputs, _legacy_key
    data, context = _inputs()
    extras = {'no_position_contract_version': 'explicit-cover-stop:v1',
              'short_setup_feedback_contract': 'schema-price-fields:v1'} if agent == 19 else {}
    old = _legacy_key(agent, data, context, output_version='agent-output:role-evidence:v4', extra_fields=extras)
    current = step_cache.build_agent_step_cache_key(agent, data, context, 'gemini-test', 'unchanged source')
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'get_cache_json', {old: {'text': 'old normalized evidence'}}.get)
    assert step_cache.get_cached_agent_step(current) is None
