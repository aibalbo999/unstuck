"""The renderer owns arithmetic; it may not silently correct model assertions."""
from copy import deepcopy
import json

import pytest

from structured_output_runtime import process_agent_response
from industry_output_completion import industry_output_issues
from summary_consistency import summary_issues


DATA = {'ticker': '6282.TW', 'financial_currency': 'TWD',
        'net_income_ttm_raw': 984595972.65, 'free_cash_flow_raw': -168490256,
        'analysis_input_hash': 'frozen-input', 'analysis_input_cutoff': '2026-10-18T12:54:26+00:00'}
BODY = ('## 總體經濟\n利率及匯率變動仍可能影響融資成本。\n'
        '## 產業供需\n需求須由正式訂單與出貨支持，不以新聞推定已實現。\n'
        '## 宏觀定調結論\n產業具有成長機會，但尚須核對訂單及現金流；'
        '若需求未落實或融資成本增加，投資風險仍高，不應僅以題材推定改善。')


def process(body=BODY, data=None, mode='v1', finish='STOP', **extra):
    context = {'pipeline_id': mode, 'data': deepcopy(data if data is not None else DATA),
               'analyses': {}, 'structured_outputs': {}}
    raw = json.dumps({'as_of_date': '2026-10-18', 'confidence': 'medium',
        'evidence_items': [{'finding': '訂單實現仍須核對。', 'source_refs': ['data.net_income_ttm_raw'],
            'freshness_note': '財務期間尚未確認。', 'counterevidence': '融資成本可能增加。'}],
        'analysis_markdown': body, **extra}, ensure_ascii=False)
    text = process_agent_response(11, raw, context, completion_diagnostics={'finish_reasons': [finish]})
    return context, text, context['structured_outputs'][11]


@pytest.mark.parametrize('mode', ['v1', 'v2', 'v3', 'v4'])
def test_all_modes_render_bound_amount_period_without_model_retyping(mode):
    context, text, output = process(mode=mode)
    assert not industry_output_issues(text, context['data'], output)
    assert output['model_analysis_markdown'] == BODY
    assert output['financial_basis']['facts']['net_income_ttm_raw']['amount_twd'] == '984595972.65'
    assert output['financial_basis']['facts']['free_cash_flow_raw']['amount_yi_twd'] == '-1.68490256'
    assert '9.8459597265 億元' in text and '-1.68490256 億元' in text
    assert '起訖期間尚未核實' in text
    assert output['financial_basis']['facts']['free_cash_flow_raw']['source_period_label'] is None
    assert '即期自由現金流' in text
    assert context['data'] == DATA


@pytest.mark.parametrize('claim', [
    'TTM 稅後淨利為 0.9846 億元。',
    'TTM 自由現金流為正 1.68 億元。',
    'TTM 起訖期間已完全經官方核實。',
    'TTM 起訖期間已核實，但年度期間尚未確認。',
])
def test_generated_basis_does_not_hide_wrong_model_claims(claim):
    context, text, output = process(BODY + '\n' + claim)
    assert industry_output_issues(text, context['data'], output)
    assert output['output_completion']['status'] == 'incomplete'


@pytest.mark.parametrize('wording', [
    '來源稱 TTM，起訖期間尚未完全官方核實。',
    '來源稱 TTM，目前無法證實涵蓋哪十二個月。',
    'TTM 自由現金流為負 0.1685 十億新臺幣（自由現金流淨流出約 1.68 億元）。',
])
def test_valid_wording_and_outflow_are_not_false_positive(wording):
    context, text, output = process(BODY + '\n' + wording)
    assert not industry_output_issues(text, context['data'], output)
    assert not summary_issues('研究分類：持有。' + wording, {'data': DATA, 'parsed': {'recommendation': {'建議': '持有'}}})


def test_current_input_and_exact_model_body_are_required_not_model_supplied_receipt():
    context, text, output = process(financial_basis={'facts': {'net_income_ttm_raw': {'amount_twd': '0'}}})
    assert output['financial_basis']['facts']['net_income_ttm_raw']['amount_twd'] == '984595972.65'
    assert industry_output_issues(text, {**DATA, 'net_income_ttm_raw': 123}, output)
    changed = deepcopy(output)
    changed['model_analysis_markdown'] += 'changed'
    assert industry_output_issues(text, DATA, changed)


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf')])
def test_missing_invalid_raw_input_is_explicit_not_zero(value):
    data = {**DATA, 'net_income_ttm_raw': value}
    context, text, output = process(data=data)
    assert output['financial_basis']['facts']['net_income_ttm_raw']['amount_twd'] is None
    assert 'TTM 稅後淨利為 0' not in text
    assert 'TTM 淨利無法確認' in text


def test_provider_truncation_stays_rejected_before_fact_rendering():
    context, text, output = process(finish='MAX_TOKENS')
    assert industry_output_issues(text, DATA, output)
    assert 'financial_basis' not in output


@pytest.mark.parametrize('amount', [10 ** 400, '168490256', False])
def test_untyped_or_unbounded_scalars_cannot_become_financial_facts(amount):
    from financial_fact_binding import financial_basis
    basis = financial_basis({**DATA, 'free_cash_flow_raw': amount})
    assert basis['facts']['free_cash_flow_raw']['amount_twd'] is None


def test_arbitrary_period_metadata_or_annual_values_cannot_certify_a_scalar():
    from financial_fact_binding import financial_basis
    basis = financial_basis({**DATA, 'free_cash_flow_period': '2025',
        'net_income_ttm_period': {'verified': True, 'start': '2025-01-01', 'end': '2025-12-31'},
        'years': [2025], 'net_income_history': [0.98459597265]})
    assert all(fact['period_status'] == 'unverified' and fact['period_start'] is None
               for fact in basis['facts'].values())


@pytest.mark.parametrize('options', [{}, {'compact': True}, {'compact_json': True}, {'dense': True}])
def test_financial_prompts_share_exact_scalar_basis_without_changing_raw_data(options):
    from prompt_builder import format_data_for_prompt
    data = {**DATA, 'company_name': '康舒'}
    before = deepcopy(data)
    prompt = format_data_for_prompt(data, **options)
    payload = json.JSONDecoder().raw_decode(prompt.split('【財務資料 JSON】\n', 1)[1])[0]
    income = payload['ttm_financials']['net_income_basis']
    fcf = payload['cash_flow']['free_cash_flow_basis']
    assert income['amount_yi_twd'] == '9.8459597265'
    assert fcf['amount_yi_twd'] == '-1.68490256'
    assert income['period_status'] == fcf['period_status'] == 'unverified'
    assert fcf['source_period_label'] is None and data == before


@pytest.mark.parametrize('body', [
    'TTM 自由現金流淨流出約 +1.68 億元。',
    'TTM 自由現金流淨流入約 1.68 億元。',
    'TTM 自由現金流淨流出約 0.168 億元。',
])
def test_explicit_wrong_sign_and_tenfold_errors_remain_blocked(body):
    context, text, output = process(BODY + '\n' + body)
    assert industry_output_issues(text, DATA, output)
    assert summary_issues('研究分類：持有。' + body,
        {'data': DATA, 'parsed': {'recommendation': {'建議': '持有'}}})


@pytest.mark.parametrize('claim', [
    '即期自由現金流為正 1.68 億元。',
    '即期自由現金流淨流出約 0.168 億元。',
    '同業成長趨緩，本公司 TTM 稅後淨利為 0.9846 億元。',
    '2025 年需求疲弱，本公司 TTM 稅後淨利為 0.9846 億元。',
    'TTM 涵蓋 2025 年 10 月至 2026 年 9 月。',
    'TTM 稅後淨利的涵蓋期間：2025-10-01 至 2026-09-30。',
    '自由現金流已經官方核實為近十二個月。',
])
def test_reviewed_false_accepts_are_blocked_in_body_and_summary(claim):
    context, text, output = process(BODY + '\n' + claim)
    assert industry_output_issues(text, DATA, output)
    assert summary_issues('研究分類：持有。' + claim,
        {'data': DATA, 'parsed': {'recommendation': {'建議': '持有'}}})


@pytest.mark.parametrize('currency', [None, 'USD'])
def test_unknown_currency_cannot_hide_a_twd_assertion(currency):
    data = {**DATA, 'financial_currency': currency}
    context, text, output = process(BODY + '\n本公司 TTM 稅後淨利為 9.846 億新臺幣。', data=data)
    assert industry_output_issues(text, data, output)


def test_receipt_identity_tampering_cannot_pass_cache_or_current_gate():
    from industry_output_completion import cached_industry_valid
    context, text, output = process()
    output['output_completion']['raw_sha256'] = 'f' * 64
    assert industry_output_issues(text, DATA, output)
    assert not cached_industry_valid({'text': text, 'structured_output': output})


def test_invalid_schema_retains_rejection_and_blocks_stale_passed_publication():
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    context, text, output = process(evidence_items=[])
    assert output['output_completion']['status'] == 'incomplete'
    assert 'financial_basis' not in output
    context['final_audit'] = {'status': 'passed', 'critical': [], 'warnings': []}
    with pytest.raises(ReportPublicationBlockedError):
        assert_report_publishable(context)


@pytest.mark.parametrize('claim', [
    '2025 年度資料涵蓋 2025 年，TTM 起訖期間未核實。',
    '同業 TTM 自由現金流為正 1.68 億元。',
    '來源稱 TTM，期間未經官方確認；年度資料涵蓋 2025 年。',
    '若未來 TTM 涵蓋 2027 年，仍須另有正式來源確認。',
])
def test_annual_peer_and_hypothetical_periods_are_not_issuer_certification(claim):
    context, text, output = process(BODY + '\n' + claim)
    assert not industry_output_issues(text, DATA, output)


@pytest.mark.parametrize('claim', [
    '2025 年自由現金流的期間為 2025 年 1 月至 12 月。',
    '2025 年年度財報已經官方核實，TTM 起訖期間尚未確認。',
    'TTM 稅後淨利換算已經確認，起訖期間尚未核實。',
    '## 同業比較\n| 期間 | 指標 | 金額 |\n| --- | --- | --- |\n| TTM | 自由現金流 | -2.50 億元 |',
])
def test_annual_arithmetic_and_peer_table_do_not_certify_current_period(claim):
    _, text, output = process(BODY + '\n' + claim)
    assert not industry_output_issues(text, DATA, output)


@pytest.mark.parametrize('claim', [
    'TTM 稅後淨利採用保存輸入。其涵蓋期間為 2025-10-01 至 2026-09-30。',
    'TTM 稅後淨利採用保存輸入；其涵蓋期間為 2025-10-01 至 2026-09-30。',
    'TTM 稅後淨利採用保存輸入\n其涵蓋期間為 2025-10-01 至 2026-09-30。',
    '## TTM 稅後淨利\n涵蓋期間為 2025-10-01 至 2026-09-30。',
    'TTM 金額未變，涵蓋 2025 年 10 月至 2026 年 9 月。',
])
def test_period_assertions_keep_subject_but_not_other_clause_negation(claim):
    from summary_consistency import summary_issues
    _, text, output = process(BODY + '\n' + claim)
    assert industry_output_issues(text, DATA, output)
    assert summary_issues('研究分類：持有。' + claim,
        {'data': DATA, 'parsed': {'recommendation': {'建議': '持有'}}})
