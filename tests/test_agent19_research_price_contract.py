"""Research-price guidance agrees with the existing execution contract."""
import copy
import json
from pathlib import Path

import pytest

import prompt_rules
import structured_output_models
from agent_runtime.prompting import ANALYSIS_PROMPTS, build_prompt
from agent_runtime.repair_reflection import build_audit_retry_instruction
from agent_runtime.step_cache import build_agent_step_cache_key
from final_audit_mode_contracts import v3_short_setup_contract_issues
from google_prompt_safety import sanitize_google_prompt
from structured_output_recommendation_outputs import ShortSetup
from trade_execution_contract import parse_price_range

RULES = Path(__file__).parents[1] / 'backend/prompts/runtime_rules.json'
OLD_FIELDS = {
    'entry_trigger': '做空或避免的可驗證觸發條件',
    'downside_target': '有證據支持的下行目標或明確資料不足',
    'cover_stop': '防軋空回補停損條件',
}
OLD_DATA_RULE = '必須明確列出做空觸發條件（Catalyst for crash）與防軋空停損點（Stop-loss level）；若資料不足，仍需給出可監控條件與保守停損邏輯。'


def context():
    data = {'ticker': 'TEST.TW', 'company_name': '測試公司', 'current_price': 26,
            'technical_indicators': {'sma_20': 34.37}}
    return {'data': data, 'pipeline_id': 'v3', 'analyses': {}, 'structured_outputs': {}}


def rendered(ctx, agent=19):
    return sanitize_google_prompt(build_prompt(agent, ctx['data'], ctx))


@pytest.mark.parametrize('repair', [False, True])
def test_initial_and_repair_wire_example_require_short_prices_but_allow_waiting(repair):
    ctx = context()
    if repair:
        ctx['_audit_retry_instruction'] = build_audit_retry_instruction(19, ['entry_zone 價格缺失'], context=ctx, data=ctx['data'])
    prompt = rendered(ctx)
    block = prompt.split('"short_setup": {', 1)[1].split('}', 1)[0]
    example = json.loads('{' + block + '}')
    for name in OLD_FIELDS:
        assert 'SHORT' in example[name] and '價格' in example[name]
        assert '非SHORT' in example[name]
    assert '來源路徑、觀測期間、原值及推導方法' in prompt
    assert '不得自動挑選均線' in prompt
    assert '純事件條件' in prompt and '等待' in prompt
    assert '強迫選擇 AVOID' in prompt


@pytest.mark.parametrize('entry,stop,label,valid', [
    ('NT$30–31', 'NT$34', '放空', True),
    ('月線附近', '突破近期高點', '放空', False),
    ('NT$30–35', 'NT$32', '放空', False),
    ('目前不建立空方部位；等待現金流轉正後重新評估。', 'N/A', '避免', True),
    ('等待現金流轉正後建立空單', 'N/A', '避免', False),
])
def test_research_scenarios_use_unchanged_parser_and_gate(entry, stop, label, valid):
    ctx = context()
    assert 'short_setup' in rendered(ctx)
    setup = ShortSetup.model_validate({'entry_trigger': entry, 'cover_stop': stop,
        'downside_target': 'NT$22' if label == '放空' else 'N/A',
        'squeeze_risk': '量價急升可能引發軋空，需重新評估風險',
        'thesis_invalidation': '現金流轉正後重新評估'}).model_dump()
    before = copy.deepcopy(setup)
    assert (not v3_short_setup_contract_issues(setup, recommendation=label)) is valid
    assert setup == before
    if entry == 'NT$30–35':
        assert parse_price_range(entry) == (30, 35)
    if entry == '月線附近':
        assert parse_price_range(entry) is None  # Do not fill source SMA20 automatically.


def test_only_agent19_prompt_content_changes_and_invalidates_its_step_key(monkeypatch):
    current = json.loads(RULES.read_text())
    old = copy.deepcopy(current)
    lines = old['structured_agent_instructions']['19']['schema_lines']
    for i, line in enumerate(lines):
        for key, value in OLD_FIELDS.items():
            if line.strip().startswith(f'"{key}":'):
                lines[i] = f'    "{key}": "{value}",'
    rules = old['data_enrichment_instructions']['19']['rules']
    index = next(i for i, rule in enumerate(rules) if rule.startswith('必須明確列出做空觸發條件'))
    rules[index] = OLD_DATA_RULE
    rules[:] = [rule for rule in rules if not rule.startswith('研究情境價格可依本次提供的來源')]
    ctx = context()
    # Freeze global version to isolate the content-key boundary. The existing
    # process-wide runtime_rules fingerprint may invalidate more roles in new jobs.
    ctx['prompt_version'] = 'same-input-and-version'
    before = {n: rendered(copy.deepcopy(ctx), n) for n in sorted(ANALYSIS_PROMPTS)}
    with monkeypatch.context() as patch:
        patch.setattr(prompt_rules, 'load_runtime_prompt_rules', lambda *_: old)
        patch.setattr(structured_output_models, 'STRUCTURED_AGENT_INSTRUCTIONS', prompt_rules.build_structured_agent_instructions())
        legacy = {n: rendered(copy.deepcopy(ctx), n) for n in before}
    assert before[19] != legacy[19]
    assert all(before[n] == legacy[n] for n in before if n != 19)
    key = lambda p: build_agent_step_cache_key(19, ctx['data'], ctx, 'gemini-test', p)
    assert key(before[19]) != key(legacy[19])
