"""A summary sees replayed official income separately from an undated quote."""
from copy import deepcopy
from test_official_income_claims import selected, TEXT


def test_summary_prompt_includes_qualified_official_income_without_rebinding_quote():
    from summary_consistency import summary_reference_prompt, summary_issues
    data = selected()
    context = {'data': data, 'parsed': {'recommendation': {'建議': '避免'}}}
    before = deepcopy(data)
    prompt = summary_reference_prompt(context)
    assert '【另列官方個別淨利，非原 quote 的期間認證】' in prompt
    assert '2025-07-01' in prompt and '2026-06-30' in prompt
    assert '0.032' in prompt and 'TWD' in prompt
    assert 'raw_response_path' not in prompt and 'official-response-evidence' not in prompt
    assert '不將原 quote 金額混用為此期間的官方淨利' in prompt
    assert data == before and data['net_income_ttm_raw'] == 860640000
    assert not summary_issues('研究分類：避免。' + TEXT, context)


def test_invalid_official_reference_cannot_enter_summary_prompt():
    from summary_consistency import summary_reference_prompt
    data = selected()
    data['official_financial_projection']['sha256'] = '0' * 64
    prompt = summary_reference_prompt({'data': data})
    assert '【另列官方個別淨利' not in prompt
    assert '8.6064' in prompt and '起訖期間尚未核實' in prompt


def test_summary_cannot_call_income_official_when_its_own_scope_is_unbound():
    from summary_consistency import summary_issues
    context = {'data': selected(), 'parsed': {'recommendation': {'建議': '避免'}}}
    text = '研究分類：避免。官方個別 TTM（2025-07-01 至 2026-06-30）淨利為 0.032 億元。'
    assert any('摘要官方財報來源資格不足' in item for item in summary_issues(text, context))
