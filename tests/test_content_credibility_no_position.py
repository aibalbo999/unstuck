"""Only verified mode-C no-position contracts make target direction inapplicable."""
import copy

import pytest

from reporting.content_credibility import evaluate_content_credibility
from reporting.content_credibility_alignment import evaluate_recommendation_target_alignment


def setup():
    return {
        'entry_trigger': '等待後續財測、毛利率與估值證據確認後重新評估；目前觀望，不開倉。',
        'downside_target': '資料不足，需重新產生可驗證下行目標',
        'cover_stop': '不適用，目前不建立空方部位。',
        'squeeze_risk': '借券與空單資料不足，禁止建立積極空方部位',
        'thesis_invalidation': '若後續財報或財測顯示基本面改善，須重新評估空方假設。',
    }


def evaluate(**overrides):
    values = dict(recommendation_present=True, recommendation_label='避免',
                  current_price=30.5, main_target=None, pipeline_id='v3', short_setup=setup())
    values.update(overrides)
    return evaluate_recommendation_target_alignment(**values)


def test_explicit_no_position_reports_not_applicable_not_passed():
    result = evaluate()
    assert result['warnings'] == [] and result['blocking_issues'] == []
    check = result['checks'][0]
    assert check['id'] == 'recommendation_target_alignment'
    assert check['status'] == 'not_applicable'
    assert check['details']['contract_scope'] == 'v3_explicit_no_position'
    assert check['details']['contract_verified'] is True
    assert check['details']['analysis_completeness'] == 'not_evaluated'
    assert check['details']['target_price'] is None


@pytest.mark.parametrize('label', ['買入', '持有', '放空', 'N/A', '', '未定'])
def test_other_or_unknown_direction_is_never_exempt(label):
    result = evaluate(recommendation_label=label)
    assert result['checks'][0]['status'] == 'warning'


@pytest.mark.parametrize('pipeline', ['', 'v1', 'v2'])
def test_other_modes_without_explicit_supported_contract_keep_warning(pipeline):
    assert evaluate(pipeline_id=pipeline)['warnings'][0]['id'] == 'missing_price_alignment_inputs'


@pytest.mark.parametrize(('field', 'value'), [
    ('entry_trigger', '等待財報，保持觀望。'),
    ('entry_trigger', '不是不開倉'),
    ('entry_trigger', '不開倉是假設，等待財報。'),
    ('entry_trigger', '目前不開倉；跌破 25 元後放空。'),
    ('entry_trigger', '目前不開倉；等待 25 元重新評估。'),
    ('entry_trigger', '目前不開倉；維持現有空單。'),
    ('cover_stop', '不適用，目前不建立空方部位；既有部位繼續持有。'),
    ('cover_stop', 'N/A'),
    ('cover_stop', '不适用'),
    ('cover_stop', '不適用，目前不建立空方部位；35 元回補。'),
    ('downside_target', '資料不足，暫定 25 元'),
    ('downside_target', 0),
    ('downside_target', -10),
    ('downside_target', '目標仍具下行空間'),
    ('squeeze_risk', 'N/A'),
    ('thesis_invalidation', 'N/A'),
])
def test_missing_or_conflicting_contract_evidence_never_exempts(field, value):
    source = setup()
    source[field] = value
    assert evaluate(short_setup=source)['warnings'][0]['id'] == 'missing_price_alignment_inputs'


def test_existing_price_direction_blockers_are_unchanged():
    for label, price, issue in [('買入', 20, 'buy_target_below_current_price'),
                                ('放空', 40, 'bearish_recommendation_high_target_price')]:
        result = evaluate(recommendation_label=label,
                          main_target={'price': price, 'source': 'recommendation.12個月'})
        assert result['blocking_issues'][0]['id'] == issue
    result = evaluate(main_target={'price': 20, 'source': 'recommendation.12個月'})
    assert result['checks'][0]['status'] != 'not_applicable'


def test_aggregate_keeps_quality_warnings_and_fallback_disclosure_without_mutation():
    context = {
        'pipeline_id': 'v3', 'data': {'current_price': 30.5},
        'parsed': {'recommendation': {'建議': '避免'}, 'short_setup': setup()},
        'analyses': {19: 'Agent 19 未能提供完整結構化輸出，系統改用保守 fallback。目前不建立新部位。'},
        'deterministic_fallbacks': [{'agent_num': 19, 'reason': 'invalid_output'}],
        'final_audit': {'status': 'passed', 'critical': [], 'warnings': ['市場來源尚未完成評估']},
    }
    original = copy.deepcopy(context)
    result = evaluate_content_credibility(context)
    alignment = next(c for c in result['checks'] if c['id'] == 'recommendation_target_alignment')
    assert alignment['status'] == 'not_applicable'
    assert not any(i['id'] == 'missing_price_alignment_inputs' for i in result['warnings'])
    assert any(i['id'] == 'final_audit_warning' for i in result['warnings'])
    assert result['status'] == 'warning'
    assert context == original


def test_plain_avoid_without_short_contract_still_requires_alignment_inputs():
    result = evaluate(short_setup={})
    assert result['warnings'][0]['id'] == 'missing_price_alignment_inputs'


def test_normalized_avoid_output_preserves_explicit_no_position_for_report_gate():
    import json
    from structured_output_runtime import process_agent_response
    from test_google_recommendation_decode import _payload

    payload = _payload('避免')
    for key in payload['recommendation']:
        if '目標' in key or '潛力' in key:
            payload['recommendation'][key] = '資料不足'
    payload['short_setup'] = setup()
    context = {'pipeline_id': 'v3', 'data': {'current_price': 26.0}}
    process_agent_response(19, json.dumps(payload, ensure_ascii=False), context, model_id='gemini-test')
    output = context['structured_outputs'][19]
    context['parsed'] = {key: output[key] for key in ('recommendation', 'short_setup')}
    result = evaluate_content_credibility(context)
    alignment = next(c for c in result['checks'] if c['id'] == 'recommendation_target_alignment')
    assert alignment['status'] == 'not_applicable'
    assert alignment['details']['contract_verified'] is True
    assert not any(i['id'] == 'missing_price_alignment_inputs' for i in result['warnings'])
    assert context['structured_outputs'][19]['analysis_markdown'] == payload['analysis_markdown']


@pytest.mark.parametrize('label', ['持有，但避免追高', '賣出', '減碼'])
def test_normalized_avoid_alias_cannot_hide_an_existing_position(label):
    _assert_normalized_warning(label, setup())


@pytest.mark.parametrize(('field', 'value'), [
    ('entry_trigger', '目前不開倉；維持現有空單。'),
    ('entry_trigger', '目前不開倉；跌破 25 元後放空。'),
    ('entry_trigger', '等待財報，保持觀望。'),
    ('cover_stop', '不適用，目前不建立空方部位；既有部位繼續持有。'),
    ('cover_stop', 'N/A'),
    ('cover_stop', '不適用，目前不建立空方部位；35 元回補。'),
    ('downside_target', '25'),
])
def test_normalization_cannot_manufacture_no_position_evidence(field, value):
    source = setup()
    source[field] = value
    _assert_normalized_warning('避免', source)


def _assert_normalized_warning(label, short_setup):
    import json
    from structured_output_runtime import process_agent_response
    from test_google_recommendation_decode import _payload
    payload = _payload(label)
    for key in payload['recommendation']:
        if '目標' in key or '潛力' in key:
            payload['recommendation'][key] = '資料不足'
    payload['short_setup'] = short_setup
    context = {'pipeline_id': 'v3', 'data': {'current_price': 30.5}}
    process_agent_response(19, json.dumps(payload, ensure_ascii=False), context, model_id='gemini-test')
    output = context['structured_outputs'][19]
    context['parsed'] = {key: output[key] for key in ('recommendation', 'short_setup')}
    result = evaluate_content_credibility(context)
    check = next(c for c in result['checks'] if c['id'] == 'recommendation_target_alignment')
    assert check['status'] == 'warning'
