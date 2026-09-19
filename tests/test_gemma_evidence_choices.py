import json
import pytest
import gemma_evidence_batches as evidence


def batch_fixture():
    value = {'price_twd': -12.5, 'zero': 0, 'missing': None, 'flag': False,
             'a/b~c': {'date': '2026-09-19'}, 'nested': [7, {'flow': -19}],
             'long_source': '完整反證不得丟棄' * 100}
    return {'batch_id': 'scope:0', 'agent_num': 23, 'identity': {},
            'records': [{'record_id': 'r0', 'path': '/evidence', 'text': evidence.encode(value)}]}


def test_choices_resolve_original_scalars_without_rewriting_or_losing_full_source():
    batch = batch_fixture()
    choices = evidence.evidence_choices(batch)
    by_pointer = {v['pointer']: k for k, v in choices.items()}
    selected = [by_pointer[k] for k in ('/price_twd', '/zero', '/missing', '/flag', '/a~1b~0c/date')]
    result = evidence.resolve_choices(batch, {'batch_id': batch['batch_id'], 'choices': selected})
    assert [r['quote'] for r in result['observations']] == [
        '"price_twd":-12.5', '"zero":0', '"missing":null', '"flag":false', '"date":"2026-09-19"']
    assert len(evidence.validate_observations(batch, result)) == 5
    assert '/long_source' not in by_pointer
    assert '/nested/1/flow' in by_pointer
    wire = json.loads(evidence.batch_prompt(batch).split('\n')[-1])
    assert wire['records'] == batch['records']
    assert '完整反證不得丟棄' * 100 in wire['records'][0]['text']
    assert evidence.resolve_choices(batch, {'batch_id': batch['batch_id'], 'choices': []})['observations'] == []


@pytest.mark.parametrize('mutation', ['wrong_id', 'extra', 'unknown', 'boolean', 'string', 'duplicate', 'too_many', 'object', 'quote'])
def test_choices_fail_closed_on_untrusted_selections(mutation):
    batch = batch_fixture()
    response = {'batch_id': batch['batch_id'], 'choices': [0]}
    if mutation == 'wrong_id': response['batch_id'] = 'another-company'
    if mutation == 'extra': response['text'] = 'invented'
    if mutation == 'unknown': response['choices'] = [99999]
    if mutation == 'boolean': response['choices'] = [True]
    if mutation == 'string': response['choices'] = ['0']
    if mutation == 'duplicate': response['choices'] = [0, 0]
    if mutation == 'too_many': response['choices'] = list(range(6))
    if mutation == 'object': response['choices'] = {'0': 'anything'}
    if mutation == 'quote': response = {'batch_id': batch['batch_id'], 'observations': [{'record_id': 'r0', 'quote': 'invented'}]}
    with pytest.raises(evidence.EvidenceBatchInvalid): evidence.resolve_choices(batch, response)


def test_cache_identity_includes_extractor_model_and_protocol(monkeypatch):
    prompt = '【財務資料 JSON】\n' + evidence.encode({'price': 12.5}) + '\n\n【使用規則】'
    original = evidence.plan_batches(22, prompt)[0]['batch_id']
    monkeypatch.setattr(evidence, 'MODEL', 'other-extractor')
    assert evidence.plan_batches(22, prompt)[0]['batch_id'] != original


def test_trigger_route_is_distinct_from_extractor(monkeypatch):
    from agent_runtime import gemma_evidence_runtime as runtime
    monkeypatch.setattr(runtime, 'GEMMA_EVIDENCE_BATCHING_ENABLED', True)
    monkeypatch.setattr(runtime, 'estimate_agent_input_tokens', lambda *args: 20000)
    assert runtime.MODEL == 'gemma-4-26b-a4b-it'
    assert runtime.should_batch(22, 'gemma-4-31b-it', 'source', {})
    assert not runtime.should_batch(22, runtime.MODEL, 'source', {})


@pytest.mark.parametrize('entry', ['async', 'sync'])
def test_extractor_failure_is_attributed_to_extractor_and_keeps_fallback_source(monkeypatch, entry):
    import asyncio
    from agent_runtime import single_agent_admission as admission, gemma_evidence_runtime as runtime
    from agent_runtime.retry_policy import AgentServerError
    monkeypatch.setattr(runtime, 'should_batch', lambda *args: True)
    def fail(*args): raise AgentServerError('504 UNAVAILABLE')
    async def fail_async(*args): return fail(*args)
    monkeypatch.setattr(runtime, 'collect_evidence', fail)
    monkeypatch.setattr(runtime, 'collect_evidence_async', fail_async)
    context = {}
    args = (23, runtime.TRIGGER_MODEL, 'complete source', context, object())
    kwargs = {'has_fallback': True, 'evidence_notes': ''}
    if entry == 'async': result = asyncio.run(admission.admit_model_input_async(*args, **kwargs))
    else: result = admission.admit_model_input_sync(*args, **kwargs)
    assert not result.call_provider and result.evidence_notes == ''
    events = context['_runtime_events']
    assert events[-1]['metadata']['model_id'] == runtime.MODEL
    assert '504' in result.last_error
