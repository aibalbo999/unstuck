"""An industry completion receipt cannot hide truncation or a missing loss."""
import asyncio
from copy import deepcopy
import json

import pytest

from industry_output_completion import POLICY, industry_output_issues
from structured_output_runtime import process_agent_response


DATA = {'ticker': '2367.TW', 'company_name': '燿華', 'financial_currency': 'TWD',
        'net_income_ttm_raw': -459064563.75}
COMPLETE = ('## 總體經濟\n高利率增加融資成本，須同時保留匯率反向波動的風險。\n'
            '## 產業週期與供需\n車用與衛星需求仍須實際訂單佐證，不能只以題材推定成長。\n'
            'TTM 稅後淨利為 -4.59 億元（淨損）。來源稱TTM，但起訖期間尚未核實，不與年度淨利混用。\n'
            '## 宏觀定調結論\n需求轉型具有機會，但虧損與融資成本使風險仍高；'
            '只有後續正式訂單與現金流改善才支持重新評估，不能由新聞單獨確認。')


def wire(text):
    return json.dumps({'as_of_date': '2026-10-18', 'confidence': 'medium',
        'evidence_items': [{'finding': '原始TTM淨利仍為負，不能以年度淨利代替。',
            'source_refs': ['data.net_income_ttm_raw'], 'freshness_note': '來源起訖日未核實。',
            'counterevidence': '年度淨利不代表同一TTM期間。'}], 'analysis_markdown': text}, ensure_ascii=False)


def run(text=COMPLETE, diagnostics=None, data=None):
    context = {'pipeline_id': 'v2', 'data': deepcopy(data or DATA), 'analyses': {}, 'structured_outputs': {}}
    result = process_agent_response(11, wire(text), context, completion_diagnostics=
        diagnostics if diagnostics is not None else {'finish_reasons': ['STOP']})
    return context, result, context['structured_outputs'][11]


def test_full_stop_response_has_bound_receipt_and_retains_negative_amount():
    context, result, output = run()
    assert COMPLETE in result
    assert output['evidence_items'][0]['source_refs'] == ['data.net_income_ttm_raw']
    assert output['output_completion']['contract_version'] == POLICY
    assert output['output_completion']['status'] == 'complete'
    assert not industry_output_issues(result, context['data'], output)
    assert context['data'] == DATA


@pytest.mark.parametrize('text,diagnostics,reason', [
    (COMPLETE, {'finish_reasons': ['MAX_TOKENS']}, 'provider_output_incomplete'),
    (COMPLETE, {}, 'provider_completion_unconfirmed'),
    (COMPLETE, {'finish_reasons': ['STOP'], 'stream_completed': False}, 'provider_output_incomplete'),
    (COMPLETE.replace('-4.59', '-0.46'), {'finish_reasons': ['STOP']}, 'incorrect_current_ttm_net_income_amount'),
    (COMPLETE.replace('TTM 稅後淨利', '2025 年稅後淨利'), {'finish_reasons': ['STOP']}, 'missing_current_ttm_net_income_amount'),
    (COMPLETE.replace('TTM 稅後淨利', '同業 TTM 稅後淨利'), {'finish_reasons': ['STOP']}, 'missing_current_ttm_net_income_amount'),
    (COMPLETE.split('## 宏觀定調結論')[0] + '## 宏觀定調結論\n* **理由：**',
     {'finish_reasons': ['STOP']}, 'missing_substantive_industry_conclusion'),
    (COMPLETE.replace('起訖期間尚未核實', '資料已經完全確認'), {'finish_reasons': ['STOP']}, 'unsupported_ttm_period_certification'),
])
def test_truncation_wrong_units_owner_period_and_empty_conclusion_stay_rejected(text, diagnostics, reason):
    if reason == 'missing_current_ttm_net_income_amount':
        # Raw prose alone still cannot use an annual or peer value as the
        # issuer's TTM value. The runtime now adds a separate bound fact block.
        from industry_output_completion import assess_industry_completion
        receipt = assess_industry_completion(wire(text), DATA, diagnostics)
        assert reason in receipt['issues']
        context, result, output = run(text, diagnostics)
        assert output['financial_basis']['facts']['net_income_ttm_raw']['amount_twd'] == '-459064563.75'
        assert 'TTM 稅後淨利為 -4.5906456375 億元' in result
        return
    context, result, output = run(text, diagnostics)
    assert output['output_completion']['status'] == 'incomplete'
    assert reason in output['output_completion']['issues']
    assert industry_output_issues(result, context['data'], output)


def test_missing_input_gets_explicit_gap_reason_not_a_zero_or_annual_substitution():
    line = 'TTM 淨利無法確認，來源未提供原始金額，不能沿用年度淨利或補零。'
    text = COMPLETE.replace(COMPLETE.splitlines()[4], line)
    context, result, output = run(text, data={**DATA, 'net_income_ttm_raw': None})
    assert output['output_completion']['status'] == 'complete'
    assert '4.59' not in result and context['data']['net_income_ttm_raw'] is None


def test_current_receipt_cannot_validate_a_changed_text_or_forget_known_truncation():
    context, result, output = run(diagnostics={'finish_reasons': ['MAX_TOKENS']})
    process_agent_response(11, wire(COMPLETE), context)
    assert 'provider_output_incomplete' in context['structured_outputs'][11]['output_completion']['issues']
    context, result, output = run()
    assert any('receipt_mismatch' in item for item in industry_output_issues(result + '附加事實', DATA, output))


def test_cached_industry_requires_complete_matching_text_and_no_loss_gap(monkeypatch):
    from agent_runtime import step_cache
    values = {}
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_ENABLED', True)
    monkeypatch.setattr(step_cache, 'AGENT_STEP_CACHE_SECONDS', 60)
    monkeypatch.setattr(step_cache, 'set_cache_json', lambda key, value, *args: values.__setitem__(key, value))
    monkeypatch.setattr(step_cache, 'get_cache_json', lambda key: values.get(key))
    context, result, _ = run()
    step_cache.store_cached_agent_step('good', agent_num=11, context=context, model_id='offline', text=result)
    assert step_cache.get_cached_agent_step('good')
    restored = {'structured_outputs': {}}
    assert step_cache.restore_cached_agent_step(restored, 11, values['good']) == result
    assert not industry_output_issues(result, DATA, restored['structured_outputs'][11])
    values['good']['text'] += 'changed'
    assert step_cache.get_cached_agent_step('good') is None
    context, result, _ = run(diagnostics={'finish_reasons': ['MAX_TOKENS']})
    step_cache.store_cached_agent_step('bad', agent_num=11, context=context, model_id='offline', text=result)
    assert 'bad' not in values


@pytest.mark.parametrize('succeeds', [True, False])
@pytest.mark.parametrize('defect', ['truncation', 'amount'])
def test_existing_once_quality_rewrite_repairs_or_preserves_the_rejection(monkeypatch, succeeds, defect):
    from agent_runtime import quality_gates as gates
    from agent_runtime.repair_state import repair_contract_issues
    context = {'ticker': '2367.TW', 'pipeline_id': 'v2', 'data': deepcopy(DATA),
               'analyses': {}, 'structured_outputs': {}, 'blocking_issues': []}
    calls = []
    bad_text = COMPLETE if defect == 'truncation' else COMPLETE.replace('-4.59', '-0.46')
    bad_finish = 'MAX_TOKENS' if defect == 'truncation' else 'STOP'
    async def initial(*args, **kwargs):
        calls.append('initial')
        return process_agent_response(11, wire(bad_text), context, completion_diagnostics={'finish_reasons': [bad_finish]})
    async def repair(*args, **kwargs):
        calls.append('repair')
        return process_agent_response(11, wire(COMPLETE if succeeds else bad_text), context,
            completion_diagnostics={'finish_reasons': ['STOP' if succeeds else bad_finish]})
    async def noop(*args, **kwargs):
        return None
    monkeypatch.setattr(gates, 'initial_or_checkpointed_draft', initial)
    monkeypatch.setattr(gates, 'run_single_agent_async', repair)
    monkeypatch.setattr(gates, 'ensure_context_digest_async', noop)
    monkeypatch.setattr(gates, 'ensure_agent_rag_context_async', noop)
    monkeypatch.setattr(gates, 'checkpoint_unvalidated_draft', noop)
    asyncio.run(gates.run_agent_with_quality_gates_async(11, context['data'], context, None))
    expected_repairs = 2 if defect == 'truncation' and not succeeds else 1
    assert calls == ['initial'] + ['repair'] * expected_repairs
    expected_quality_retry = 0 if defect == 'truncation' and succeeds else 1
    assert (context.get('agent_quality_retry_counts') or {}).get(11, 0) == expected_quality_retry
    assert context['data'] == DATA
    if succeeds:
        assert not context['blocking_issues'] and not repair_contract_issues(11, context)
    else:
        assert context['blocking_issues'] and repair_contract_issues(11, context)
        assert all(item.startswith('Agent 11 ') for item in context['blocking_issues'])


def test_known_google_routes_use_low_thinking_with_unchanged_output_cap():
    from agent_runtime.generation_config import generation_event_metadata, google_safe_agent_system_instruction
    for model in ('gemini-3-flash-preview', 'gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.5-flash-lite'):
        profile = generation_event_metadata(11, model)
        assert profile['thinking_level'] == 'low' and profile['max_output_tokens'] == 3072
        assert profile['completion_policy_version'] == POLICY
        assert '起訖期間尚未核實' in google_safe_agent_system_instruction(11, model)


def test_publication_rejects_incomplete_industry_even_with_a_stale_passed_audit():
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    context, _, _ = run(diagnostics={'finish_reasons': ['MAX_TOKENS']})
    context['final_audit'] = {'status': 'passed', 'critical': [], 'warnings': []}
    with pytest.raises(ReportPublicationBlockedError, match='Agent 11'):
        assert_report_publishable(context)
    context, _, _ = run()
    context['final_audit'] = {'status': 'passed', 'critical': [], 'warnings': []}
    assert_report_publishable(context)


def test_raw_evidence_fields_cannot_be_manufactured_by_normalizer_defaults():
    from industry_output_completion import assess_industry_completion
    payload = json.loads(wire(COMPLETE))
    del payload['evidence_items'][0]['counterevidence']
    receipt = assess_industry_completion(json.dumps(payload, ensure_ascii=False), DATA,
                                         {'finish_reasons': ['STOP']})
    assert receipt['status'] == 'incomplete'
    assert 'evidence_0_missing_counterevidence' in receipt['issues']


@pytest.mark.parametrize('limitation', ['起訖期間尚未經官方核實', '起訖日尚未經原件確認',
                                       'TTM期間未能核實', 'TTM期間尚無法確認'])
def test_explicit_unverified_period_wording_is_not_misread_as_missing(limitation):
    _, _, output = run(COMPLETE.replace('起訖期間尚未核實', limitation))
    assert output['output_completion']['status'] == 'complete'


@pytest.mark.parametrize('limitation', [
    '起訖期間尚未完全官方核實',
    '起訖期間尚未完全經官方核實',
    '起訖期間尚未經官方完全核實',
    'TTM期間尚未完全核實',
    'TTM期間未完全確認',
    '起訖期間尚未完全經原件確認',
    'TTM期間尚未完全獲來源確認',
])
def test_explicit_incomplete_verification_preserves_the_period_caution(limitation):
    context, result, output = run(COMPLETE.replace('起訖期間尚未核實', limitation))
    assert output['output_completion']['status'] == 'complete'
    assert not industry_output_issues(result, context['data'], output)
    assert limitation in result and context['data'] == DATA


@pytest.mark.parametrize('limitation', [
    '起訖期間已完全經官方核實',
    '起訖期間已經官方完全核實',
    'TTM期間已完全確認',
    '起訖期間尚未提供',
])
def test_completed_verification_or_unrelated_missingness_is_not_a_period_caution(limitation):
    from industry_output_completion import assess_industry_completion
    text = COMPLETE.replace('起訖期間尚未核實', limitation)
    assert 'missing_ttm_period_limitation' in assess_industry_completion(
        wire(text), DATA, {'finish_reasons': ['STOP']})['issues']
    _, result, output = run(text)
    if '已' in limitation:
        assert 'unsupported_ttm_period_certification' in output['output_completion']['issues']
    else:
        assert '起訖期間尚未核實' in result
        assert output['financial_basis']['facts']['net_income_ttm_raw']['period_status'] == 'unverified'


def test_unsigned_loss_magnitude_is_negative_but_explicit_positive_sign_stays_rejected():
    text = COMPLETE.replace('為 -4.59 億元（淨損）', '仍為淨損 4.59 億元')
    _, _, output = run(text)
    assert output['output_completion']['status'] == 'complete'
    _, _, output = run(text.replace('淨損 4.59', '淨損 +4.59'))
    assert 'incorrect_current_ttm_net_income_amount' in output['output_completion']['issues']


@pytest.mark.parametrize('text,expected', [
    ('TTM 稅後淨利為虧損約 NT$4.59 億元。', '-4.59'),
    ('TTM 稅後淨利並非淨損 4.59 億元。', '4.59'),
    ('TTM 稅後淨利未發生虧損 4.59 億元。', '4.59'),
    ('TTM 稅後淨利為淨損 +4.59 億元。', '+4.59'),
    ('年度營收為虧損 4.59 億元。', '4.59'),
])
def test_loss_sign_binding_preserves_explicit_sign_negation_and_metric(text, expected):
    from financial_money_claims import _AMOUNT, signed_amount_number
    assert signed_amount_number(_AMOUNT.search(text)) == expected
