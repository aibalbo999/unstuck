"""Agent 19 receives its real JSON paths, without inventing execution prices."""
import copy
import json
import os
from pathlib import Path

import pytest

from agent_runtime.repair_reflection import build_audit_retry_instruction
from agent_runtime.repair_state import repair_contract_issues
from structured_output_recommendation_outputs import ShortSetup


# Verbatim execution fields from 5314 candidates 3/4/5, 2026-09-23.
CASES = [
    ('股價反彈至月線附近遇壓，且融資餘額下滑而法人持續賣超時建立保守空方風險觀察部位', 'NT$32.50'),
    ('當單月營收年增率轉負、無人機題材進度延宕且法人籌碼與融資同步呈現大舉潰散時，可作為空方風險觀察之依據。',
     '若短線成交量再度放大且股價帶量突破近期整理區間高點，空方應嚴格執行停損。'),
    ('股價反彈至短線均線壓力區且單日成交量萎縮、法人持續賣超時建立保守空方部位',
     '短線成交量放大且股價帶量突破近期整理區間高點'),
]


def context_for(entry, stop, label='放空'):
    return {'pipeline_id': 'v3', 'data': {'ticker': '5314.TWO', 'current_price': 26},
            'analyses': {}, 'structured_outputs': {19: {
                'recommendation': {'建議': label, '長期目標（12個月）': 'NT$15'},
                'short_setup': {'entry_trigger': entry, 'downside_target': 'NT$15',
                               'cover_stop': stop, 'squeeze_risk': '須評估軋空風險',
                               'thesis_invalidation': '現金流轉正後重新評估'}}}}


def instruction(context, agent=19):
    return build_audit_retry_instruction(agent, ['entry_zone 必須是可解析的正數價格或單一明確價格區間。'],
                                         context=context, data=context['data'])


@pytest.mark.parametrize('entry,stop', CASES)
def test_real_missing_price_candidates_get_actionable_json_field_feedback(entry, stop):
    context = context_for(entry, stop)
    before = copy.deepcopy(context['structured_outputs'])
    result = instruction(context)
    assert 'short_setup.entry_trigger（通用檢查欄位 entry_zone）' in result
    assert 'short_setup.cover_stop（通用檢查欄位 stop_loss）' in result
    assert f'原值：{json.dumps(entry, ensure_ascii=False)}；價格解析：null' in result
    assert f'原值：{json.dumps(stop, ensure_ascii=False)}；價格解析：' in result
    assert ('[32.5, 32.5]' in result) == (stop == 'NT$32.50')
    assert '不得以現價、均線、目標價或其他欄位自動代填' in result
    assert context['structured_outputs'] == before


@pytest.mark.parametrize('entry', ['成交量3萬至5萬股後確認', '營收17億至20億元', '跌幅5%後確認', 'SMA20 均線附近'])
def test_diagnostics_use_execution_parser_not_first_number(entry):
    result = instruction(context_for(entry, 'NT$32.5'))
    assert f'原值：{json.dumps(entry, ensure_ascii=False)}；價格解析：null' in result


def test_range_diagnostic_preserves_full_interval_and_wrong_stop_gate():
    context = context_for('NT$30–35', 'NT$32.5')
    result = instruction(context)
    assert '價格解析：[30.0, 35.0]' in result
    assert 'short_stop_not_outside_entry' in result
    assert 'stop_loss / cover_stop 未位於完整進場區間的正確停損方向' in result
    assert any('正確停損方向' in issue for issue in repair_contract_issues(19, context))


def test_no_position_is_not_forced_to_add_prices_and_other_agents_unchanged():
    context = context_for('目前不建立空方部位；等待現金流轉正後重新評估。', 'N/A', '避免')
    result = instruction(context)
    assert '非放空分類依既有觀望契約驗證；不要求補造進場或停損價' in result
    assert 'invalid_entry_zone' not in result
    assert 'short_setup.entry_trigger（通用檢查欄位 entry_zone）' not in instruction(context, 18)


def test_response_schema_names_price_semantics_without_ticker_anchor():
    properties = ShortSetup.model_json_schema()['properties']
    for name in ('entry_trigger', 'downside_target', 'cover_stop'):
        description = properties[name].get('description', '')
        assert '價格' in description and '不得補造' in description
        assert '5314' not in description and '32.5' not in description


def test_saved_complete_candidates_receive_same_feedback_when_available():
    path = os.environ.get('AGENT19_REPAIR_CANDIDATES')
    if not path:
        pytest.skip('optional private live-candidate replay')
    from structured_output_runtime import process_agent_response
    for row in json.loads(Path(path).read_text())[3:6]:
        context = context_for('', '')
        text = process_agent_response(19, row['text'], context, model_id=row['model_id'])
        context['analyses'][19] = text
        before = copy.deepcopy(context['structured_outputs'])
        issues_before = repair_contract_issues(19, context)
        feedback = instruction(context)
        assert 'short_setup.entry_trigger（通用檢查欄位 entry_zone）' in feedback
        assert '價格解析：null' in feedback
        assert context['structured_outputs'] == before
        assert repair_contract_issues(19, context) == issues_before


def test_immediate_retry_embeds_field_feedback_after_structured_is_cleared(monkeypatch):
    from agent_runtime import quality_retry
    from agent_runtime.prompting import build_prompt
    from google_prompt_safety import sanitize_google_prompt
    context = context_for(*CASES[0])
    context['data']['company_name'] = '天剛'
    context['analyses'][19] = '原始正文'
    monkeypatch.setattr(quality_retry, 'quality_retry_model_sequence', lambda *_: ['configured-model'])
    quality_retry.install_quality_retry_context(context, 19, ['entry_zone 價格缺失'])
    assert not context['structured_outputs']
    prompt = sanitize_google_prompt(build_prompt(19, context['data'], context))
    assert 'short_setup.entry_trigger（通用檢查欄位 entry_zone）' in prompt
    assert CASES[0][0] in prompt
    assert '價格解析：[32.5, 32.5]' in prompt
    assert '不得以現價、均線、目標價或其他欄位自動代填' in prompt
