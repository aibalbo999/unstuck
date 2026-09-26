"""Already rejected research evidence must not become a reusable initial draft."""
import copy
import json

import pytest

from structured_output_runtime import process_agent_response
from test_research_completion_cache import context, memory_cache, payload


def assessed(kind):
    ctx = context()
    ctx['analyses'] = {4: '估值原文依據。', 5: '成長原文依據。'}
    value = payload()
    reconciliation = value['assumption_reconciliation']
    if kind == 'wrong_role':
        reconciliation['checks'][0]['growth_quote'] = ctx['analyses'][4]
    elif kind == 'aggregate':
        reconciliation['status'] = 'aligned'
    elif kind in ('pending_missing', 'valid_conflict'):
        reconciliation['status'] = 'conflict'
        reconciliation['pending_recalculation'] = kind == 'valid_conflict'
        for row in reconciliation['checks']:
            row.update(status='conflict', valuation_quote=ctx['analyses'][4], growth_quote=ctx['analyses'][5])
    elif kind == 'blank_rationale':
        reconciliation['checks'][0]['rationale'] = ' '
    else:
        assert kind == 'valid_unassessed'
    text = process_agent_response(7, json.dumps(value, ensure_ascii=False), ctx,
                                  completion_diagnostics={'finish_reasons': ['STOP']})
    assert ctx['structured_outputs'][7]
    return ctx, text


@pytest.mark.parametrize('kind', ['wrong_role', 'aggregate', 'pending_missing', 'blank_rationale'])
def test_known_failed_assessment_is_never_stored(kind, monkeypatch):
    cache, values = memory_cache(monkeypatch)
    ctx, text = assessed(kind)
    assert ctx['structured_outputs'][7]['assumption_reconciliation_assessment']['issues']
    before = copy.deepcopy(ctx)
    cache.store_cached_agent_step('rejected', agent_num=7, context=ctx, model_id='offline', text=text)
    assert values == {}
    assert ctx == before


@pytest.mark.parametrize('kind', ['wrong_role', 'aggregate', 'pending_missing', 'blank_rationale'])
def test_preexisting_failed_assessment_is_a_miss_and_cannot_be_restored(kind, monkeypatch):
    cache, values = memory_cache(monkeypatch)
    ctx, text = assessed(kind)
    entry = {'agent_num': 7, 'model_id': 'offline', 'text': text,
             'structured_output': copy.deepcopy(ctx['structured_outputs'][7])}
    values['old'] = entry
    assert cache.get_cached_agent_step('old') is None
    assert not cache.cached_market_context_matches({}, 7, entry, 'same prompt')
    restored = {'structured_outputs': {7: {'stale': True}}}
    assert cache.restore_cached_agent_step(restored, 7, entry) == ''
    assert 7 not in restored['structured_outputs']


@pytest.mark.parametrize('kind', ['valid_unassessed', 'valid_conflict'])
def test_honest_limitations_and_supported_conflict_remain_cacheable(kind, monkeypatch):
    cache, values = memory_cache(monkeypatch)
    ctx, text = assessed(kind)
    output = ctx['structured_outputs'][7]
    assert output['assumption_reconciliation_assessment']['issues'] == []
    cache.store_cached_agent_step('valid', agent_num=7, context=ctx, model_id='offline', text=text)
    cached = cache.get_cached_agent_step('valid')
    assert cached is not None
    restored = context()
    assert cache.restore_cached_agent_step(restored, 7, cached) == text
    assert restored['structured_outputs'][7] == output


@pytest.mark.parametrize('agent', [16, 19])
def test_other_modes_do_not_use_research_assessment_admission(agent, monkeypatch):
    cache, values = memory_cache(monkeypatch)
    ctx, text = assessed('wrong_role')
    ctx['structured_outputs'] = {agent: ctx['structured_outputs'][7]}
    cache.store_cached_agent_step('other-mode', agent_num=agent, context=ctx, model_id='offline', text=text)
    assert cache.get_cached_agent_step('other-mode') is not None
