"""Role/topic retrieval is source-bound, not permission to invent agreement."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from research_assumption_contract import TOPICS, assess_reconciliation
from research_quote_catalog import quote_catalog, resolve_quote_references
from research_quote_semantics import POLICY


MARGIN = '毛利率受到研發與管理費用壓抑，實質獲利轉化仍需要持續追蹤。'
CALCULATION = r'成長計算公式：Revenue = Base \times (1 + g)^5，公式仍需核對基期與期間。'


def reconciliation():
    return {'status': 'unassessed', 'pending_recalculation': False, 'checks': [
        {'topic': topic, 'status': 'unassessed', 'valuation_quote': '', 'growth_quote': '',
         'rationale': '尚缺同主題證據，不推定雙方假設一致。'} for topic in TOPICS]}


def test_wrong_topic_ref_is_not_resolved_even_when_unassessed():
    source = '毛利率受到研發與管理費用壓抑，實質獲利轉化仍需要持續追蹤。'
    context = {'analyses': {5: source}}
    fingerprint, catalog = quote_catalog(context)
    ref = next(key for key, item in catalog.items() if item['text'] == source)
    value = reconciliation()
    value['upstream_fingerprint'] = fingerprint
    value['checks'][-1]['growth_quote_ref'] = ref
    before = deepcopy(value)
    resolved, receipt = resolve_quote_references(value, context, 'raw')
    assert resolved == before
    assert receipt is None
    assert 'unsupported_growth_quote_ref' in assess_reconciliation(resolved, context)['issues']


def test_catalog_retains_other_topics_when_growth_candidates_fill_old_limit():
    growth = [f'營收成長候選第{index:02d}項，仍需要驗證客戶訂單持續性與市場需求。' for index in range(20)]
    margin = '毛利率受到產品組合與產能利用率影響，仍須核對資本支出與折舊。'
    context = {'analyses': {5: '\n'.join([*growth, margin])}}
    _, catalog = quote_catalog(context)
    assert any(item['text'] == margin for item in catalog.values())


def test_unterminated_source_tail_is_not_offered_as_a_complete_topic_candidate():
    tail = '- **營業利益率與淨利率**：雖然毛利率提升，但營業利益率受限於高昂研發與管理費用，2024 年為 -0.4%、202'
    context = {'analyses': {5: MARGIN + '\n' + tail}}
    _, catalog = quote_catalog(context)
    assert any(item['text'] == MARGIN for item in catalog.values())
    assert not any(item['text'] == tail for item in catalog.values())
    from research_assumption_contract import build_reconciliation_source_prompt
    assert json.dumps(tail, ensure_ascii=False)[1:-1] in build_reconciliation_source_prompt(context)


def test_legacy_unassessed_literal_is_not_reinterpreted_or_rewritten():
    source = '毛利率受到研發與管理費用壓抑，實質獲利轉化仍需要持續追蹤。'
    context = {'analyses': {5: source}}
    value = reconciliation()
    value['semantic_contract_version'] = POLICY
    value['checks'][-1]['growth_quote'] = source
    before = deepcopy(value)
    assessment = assess_reconciliation(value, context)
    assert not assessment['issues']
    assert value == before


def calculation_case():
    context = {'analyses': {5: CALCULATION}, 'structured_outputs': {}}
    fingerprint, catalog = quote_catalog(context)
    ref = next(key for key, item in catalog.items() if item.get('topic') == 'calculation')
    value = reconciliation()
    value['upstream_fingerprint'] = fingerprint
    value['checks'][-1]['growth_quote_ref'] = ref
    return context, value, ref


def test_short_topic_ref_requires_full_fingerprint_and_resolves_exact_literal():
    context, value, ref = calculation_case()
    assert ref == 'a5-calculation-1'
    before = deepcopy((value, context))
    resolved, receipt = resolve_quote_references(value, context, 'raw')
    assert resolved['checks'][-1]['growth_quote'] == CALCULATION
    assert receipt['upstream_fingerprint'] == value['upstream_fingerprint']
    assert receipt['resolutions'][0]['topic'] == 'calculation'
    assert not assess_reconciliation(resolved, context)['issues']
    assert (value, context) == before
    assert {key: item for key, item in resolved['checks'][-1].items() if key != 'growth_quote'} == {
        key: item for key, item in value['checks'][-1].items() if key != 'growth_quote'}


@pytest.mark.parametrize('mutation', ['missing', 'prefix', 'forged', 'changed_source', 'other_role_changed',
                                     'changed_leaf', 'wrong_role', 'wrong_topic', 'unknown', 'missing_quote'])
def test_short_refs_fail_closed_without_current_role_topic_and_fingerprint(mutation):
    context, value, ref = calculation_case()
    row = value['checks'][-1]
    if mutation == 'missing':
        del value['upstream_fingerprint']
    elif mutation == 'prefix':
        value['upstream_fingerprint'] = value['upstream_fingerprint'][:16]
    elif mutation == 'forged':
        value['upstream_fingerprint'] = '0' * 64
    elif mutation == 'changed_source':
        context['analyses'][5] += '\n同角色來源補充，舊指紋不得沿用。'
    elif mutation == 'other_role_changed':
        context['analyses'][4] = '估值來源更新，完整來源指紋必須重新核驗。'
    elif mutation == 'changed_leaf':
        context['structured_outputs'][5] = {'assumption': '成長假設已更新，舊片段也不代表來源未改變。'}
    elif mutation == 'wrong_role':
        row['valuation_quote_ref'] = row.pop('growth_quote_ref')
    elif mutation == 'wrong_topic':
        row['growth_quote_ref'] = ref.replace('calculation', 'growth')
    elif mutation == 'unknown':
        row['growth_quote_ref'] = 'a5-calculation-99'
    else:
        del row['growth_quote']
    before = deepcopy((value, context))
    resolved, receipt = resolve_quote_references(value, context, 'raw')
    assert resolved == value and receipt is None
    assert assess_reconciliation(resolved, context)['issues']
    assert (value, context) == before


@pytest.mark.parametrize('quote', [CALCULATION, ' ', '自行改寫成長計算公式，不能覆寫成原文。'])
def test_nonempty_quotes_are_never_overwritten_or_given_resolution_receipts(quote):
    context, value, _ = calculation_case()
    value['checks'][-1]['growth_quote'] = quote
    before = deepcopy(value)
    resolved, receipt = resolve_quote_references(value, context, 'raw')
    assert resolved == before and receipt is None
    assert bool(assess_reconciliation(resolved, context)['issues']) == (quote != CALCULATION)


@pytest.mark.parametrize('status', ['aligned', 'conflict'])
def test_retrieval_does_not_make_an_unsupported_dcf_rationale_or_status_valid(status):
    context, value, _ = calculation_case()
    value.update(status='conflict' if status == 'conflict' else 'unassessed',
                 semantic_contract_version=POLICY)
    value['checks'][-1].update(status=status, rationale='雙方 DCF 計算一致且不需重算。')
    resolved, receipt = resolve_quote_references(value, context, 'raw')
    assert receipt
    assert resolved['checks'][-1]['status'] == status
    assert resolved['pending_recalculation'] is False
    assessment = assess_reconciliation(resolved, context)
    if status == 'aligned':
        assert any(issue['reason'] == 'dcf_rationale_not_supported_by_quote' for issue in assessment['semantic_issues'])
    else:
        assert 'conflict_requires_recalculation' in assessment['issues']


def test_new_topic_refs_cannot_disable_semantics_by_omitting_model_version():
    context = {'analyses': {4: CALCULATION, 5: CALCULATION}}
    fingerprint, _ = quote_catalog(context)
    value = reconciliation()
    value['upstream_fingerprint'] = fingerprint
    value['checks'][-1].update(status='aligned', valuation_quote_ref='a4-calculation-1',
                              growth_quote_ref='a5-calculation-1', rationale='雙方 DCF 計算一致。')
    resolved, _ = resolve_quote_references(value, context, 'raw')
    assessment = assess_reconciliation(resolved, context)
    assert 'unsupported_assumption_topic_or_period' in assessment['issues']
    assert resolved['checks'][-1]['status'] == 'aligned'
    assert 'semantic_contract_version' not in resolved


def legacy_ref(source, agent, fingerprint):
    item = {'source_agent': agent, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'start': 0, 'end': len(source), 'text': source}
    digest = hashlib.sha256((fingerprint + json.dumps(item, ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    return f'a{agent}-{digest}'


def test_legacy_full_hash_refs_are_current_source_bound_and_topic_checked():
    context = {'analyses': {5: CALCULATION}}
    fingerprint, _ = quote_catalog(context)
    value = reconciliation()
    value['checks'][-1]['growth_quote_ref'] = legacy_ref(CALCULATION, 5, fingerprint)
    resolved, receipt = resolve_quote_references(value, context, 'raw')
    assert receipt and not assess_reconciliation(resolved, context)['issues']
    context['analyses'][5] += '\n來源已更新。'
    assert resolve_quote_references(value, context, 'raw') == (value, None)
    assert assess_reconciliation(resolved, context)['issues']
    context = {'analyses': {5: MARGIN}}
    fingerprint, _ = quote_catalog(context)
    value['checks'][-1]['growth_quote_ref'] = legacy_ref(MARGIN, 5, fingerprint)
    assert resolve_quote_references(value, context, 'raw') == (value, None)
    assert 'unsupported_growth_quote_ref' in assess_reconciliation(value, context)['issues']


def test_catalog_slices_are_contiguous_and_do_not_join_sources_or_roles():
    sources = {'4': ['\n  ' + CALCULATION + '\n', MARGIN], '5': [MARGIN, CALCULATION]}
    context = {'analyses': sources, 'structured_outputs': {}}
    _, catalog = quote_catalog(context)
    assert catalog
    for ref, item in catalog.items():
        role = str(item['source_agent'])
        assert ref.startswith('a' + role + '-' + item['topic'] + '-')
        witnesses = [source for source in sources[role]
                     if hashlib.sha256(source.encode()).hexdigest() == item['source_sha256']]
        assert witnesses and all(source[item['start']:item['end']] == item['text'] for source in witnesses)
    context = {'structured_outputs': {5: {'left': '成長公式的左半段', 'right': '不能和右半段拼成證據'}}}
    assert not quote_catalog(context)[1]


def test_private_native_a_stays_rejected_without_rewriting_frozen_evidence():
    path = Path('/tmp/stock-agent-five-reruns.qFkyKS/summary-industry-verification/'
                '3cf095eb80ab4f1ebdc716817896bc28.final.state.json')
    if not path.is_file():
        pytest.skip('Private native checkpoint is not distributed with tests')
    raw = path.read_bytes()
    state = json.loads(raw)
    before = deepcopy(state)
    value = state['structured_outputs']['7']['assumption_reconciliation']
    resolved, receipt = resolve_quote_references(value, state, 'offline replay only')
    assert resolved == value and receipt is None
    assessment = assess_reconciliation(resolved, state)
    assert 'unsupported_growth_quote_ref' in assessment['issues']
    assert any(item['topic'] == 'calculation' and item['field'] == 'growth_quote'
               and item['reason'] == 'dcf_rationale_not_supported_by_quote'
               for item in assessment['semantic_issues'])
    _, catalog = quote_catalog(state)
    assert not any(item['source_agent'] == 5 and item['topic'] == 'calculation' for item in catalog.values())
    assert state == before and path.read_bytes() == raw
