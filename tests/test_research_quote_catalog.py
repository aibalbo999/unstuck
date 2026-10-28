"""Current source IDs are retrieval receipts, not an evidence-gate exemption."""
from copy import deepcopy
import hashlib
import json

import pytest

from research_assumption_contract import TOPICS, assess_reconciliation, build_reconciliation_source_prompt
from research_quote_catalog import quote_catalog, resolve_quote_references
from structured_output_runtime import process_agent_response

SOURCE4 = '基本情境以原始 Forward EPS 1.70 元乘以 24 倍本益比計算，目標為 40.80 元。'
SOURCE5 = r'成長計算公式：Revenue = Base \times (1 + g)^5，公式仍需核對基期與期間。'


def setup():
    assumptions = '成長估算以2025年度為基期、預測未來五年，CapEx及毛利率假設尚需逐項核對。'
    context = {'pipeline_id': 'v1', 'data': {'current_price': 43.15},
               'analyses': {4: SOURCE4 + '\n' + assumptions, 5: SOURCE5 + '\n' + assumptions},
               'structured_outputs': {}}
    fingerprint, catalog = quote_catalog(context)
    refs = {(agent, topic): next(key for key, item in catalog.items()
             if item['source_agent'] == agent and item['topic'] == topic)
            for agent in (4, 5) for topic in TOPICS}
    value = {'status': 'conflict', 'pending_recalculation': True, 'upstream_fingerprint': fingerprint, 'checks': [
        {'topic': topic, 'status': 'conflict', 'valuation_quote': '', 'growth_quote': '',
         'valuation_quote_ref': refs[4, topic], 'growth_quote_ref': refs[5, topic],
         'rationale': '引文保留差異，尚未重算，不宣稱經濟假設一致。'} for topic in TOPICS]}
    return context, value, fingerprint, catalog


def test_current_refs_resolve_exact_backslashes_and_keep_every_other_claim():
    context, value, fingerprint, catalog = setup()
    before = deepcopy((context, value))
    resolved, receipt = resolve_quote_references(value, context, 'raw response')
    assert receipt['upstream_fingerprint'] == fingerprint
    assert receipt['raw_sha256'] == hashlib.sha256(b'raw response').hexdigest()
    for item in receipt['resolutions']:
        source = context['analyses'][item['source_agent']]
        assert source[item['start']:item['end']] == item['text']
        assert hashlib.sha256(source.encode()).hexdigest() == item['source_sha256']
        assert catalog[item['ref']]['text'] == item['text']
    assert resolved['checks'][-1]['growth_quote'] == SOURCE5
    assert resolved['pending_recalculation'] is True
    assert not assess_reconciliation(resolved, context)['issues']
    assert (context, value) == before


@pytest.mark.parametrize('defect', ['wrong_role', 'stale', 'changed_literal', 'unknown', 'missing_quote'])
def test_invalid_refs_and_nonempty_changed_quotes_fail_closed(defect):
    context, value, _, catalog = setup()
    row = value['checks'][0]
    if defect == 'wrong_role':
        row['growth_quote_ref'] = row['valuation_quote_ref']
    elif defect == 'stale':
        context['analyses'][4] += '來源已更新。'
    elif defect == 'changed_literal':
        row['growth_quote'] = SOURCE5.replace('\\times', '\\\\times')
    elif defect == 'unknown':
        row['growth_quote_ref'] = 'a5-forged'
    else:
        del row['growth_quote']
    original = deepcopy(row)
    resolved, _ = resolve_quote_references(value, context, 'raw')
    assert assess_reconciliation(resolved, context)['issues']
    if defect == 'changed_literal':
        assert resolved['checks'][0]['growth_quote'] == original['growth_quote']


def test_refs_do_not_waive_pending_recalculation_or_return_contract():
    from agent_runtime.repair_state import repair_contract_issues
    context, value, _, _ = setup()
    value['pending_recalculation'] = False
    payload = {'recommendation': {'建議': '持有', '長期目標（12個月）': 'NT$40.80'},
               'analysis_markdown': '等待更多資料，不是已確認買進條件。',
               'assumption_reconciliation': value, 'assumption_quote_resolution': {'forged': True}}
    raw = json.dumps(payload, ensure_ascii=False)
    process_agent_response(7, raw, context)
    output = context['structured_outputs'][7]
    assert output['assumption_quote_resolution']['raw_sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert 'conflict_requires_recalculation' in output['assumption_reconciliation_assessment']['issues']
    assert any('建議/報酬矛盾' in issue for issue in repair_contract_issues(7, context))
    from structured_output_normalizer import normalize_structured_output
    assert normalize_structured_output(7, output)['assumption_quote_resolution'] == output['assumption_quote_resolution']
    payload['assumption_reconciliation']['checks'][0]['growth_quote_ref'] = 'unknown'
    process_agent_response(7, json.dumps(payload, ensure_ascii=False), context)
    assert context['structured_outputs'][7]['assumption_reconciliation_assessment']['issues']
    assert not context['structured_outputs'][7]['assumption_quote_resolution'].get('forged')


def test_full_source_remains_visible_and_catalog_never_joins_roles_or_leaves():
    context, _, _, catalog = setup()
    context['structured_outputs'][5] = {'left': '短片段', 'right': '另一個短片段'}
    prompt = build_reconciliation_source_prompt(context)
    assert json.dumps(SOURCE4, ensure_ascii=False)[1:-1] in prompt
    assert json.dumps(SOURCE5, ensure_ascii=False)[1:-1] in prompt
    assert all(24 <= len(item['text']) <= 240 for item in catalog.values())
    assert len(catalog) <= 30


def test_arithmetic_aids_preserve_period_currency_sign_and_do_not_choose_labels():
    from research_decision_guidance import decision_arithmetic_prompt
    from financial_money_claims import ttm_money_reference_prompt
    context, _, _, _ = setup()
    context['structured_outputs'][4] = {'price_targets': {'基本情境': 40.8, 'invalid': True}}
    prompt = decision_arithmetic_prompt(context)
    assert '-5.4461' in prompt and '不認定情境期間' in prompt and 'invalid' not in prompt
    data = {'net_income_ttm_raw': -459064563.75, 'financial_currency': 'TWD'}
    assert '-4.5906456375 億元' in ttm_money_reference_prompt(data)
    assert '-0.45906456375 billion_twd' in ttm_money_reference_prompt(data)
    for raw in (None, True, float('nan'), float('inf')):
        assert not ttm_money_reference_prompt({**data, 'net_income_ttm_raw': raw})
    assert not ttm_money_reference_prompt({**data, 'financial_currency': 'USD'})
    assert not ttm_money_reference_prompt({**data, 'financial_currency': None})


def test_prompt_wires_refs_and_money_hints_only_to_the_intended_roles():
    from agent_runtime.prompting import build_prompt
    from google_prompt_safety import sanitize_google_prompt
    context, _, _, _ = setup()
    context['data'].update(ticker='6282.TW', company_name='康舒', financial_currency='TWD',
                           net_income_ttm_raw=-459064563.75)
    before = deepcopy(context)
    prompt = sanitize_google_prompt(build_prompt(7, context['data'], context))
    assert 'valuation_quote_ref' in prompt and 'growth_quote_ref' in prompt
    assert next(iter(quote_catalog(context)[1])) in prompt
    industry = sanitize_google_prompt(build_prompt(11, context['data'], context))
    assert '-4.5906456375 億元' in industry
    assert '當前來源的逐字片段編號' not in industry
    assert '凍結輸入金額換算參考' not in prompt
    assert context == before
