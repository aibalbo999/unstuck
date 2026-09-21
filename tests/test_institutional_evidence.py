"""2033 saved 20260921_213530: real unit/population corruption, offline only."""
import copy

import pytest

from short_term_output_validator import short_term_evidence_issues


@pytest.fixture
def data():
    return {"ticker": "2033.TW", "institutional_trading": {
        "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell",
        "lookback_trading_days": 30, "latest_date": "2026-09-21",
        "net_buy_shares_by_category": {"foreign": 1528577, "investment_trust": 0, "dealer": 70668},
        "net_buy_thousand_shares_by_category": {"foreign": 1528.58, "investment_trust": 0, "dealer": 70.67},
        "total_net_buy_shares": 1599245, "total_net_buy_thousand_shares": 1599.24,
        "last_5_trading_days_net_buy_thousand_shares": 1576.69,
        "daily_total_net_buy_last_10": [
            {"date": "2026-09-15", "net_buy_thousand_shares": -64.98},
            {"date": "2026-09-16", "net_buy_thousand_shares": 344.96},
            {"date": "2026-09-17", "net_buy_thousand_shares": 309.94},
            {"date": "2026-09-18", "net_buy_thousand_shares": 965.04},
            {"date": "2026-09-21", "net_buy_thousand_shares": 21.74},
        ],
    }}


@pytest.mark.parametrize("agent", [23, 24])
@pytest.mark.parametrize("claim", [
    "外資於近 5 個交易日呈現顯著買超，合計買超達 1,576.69 千張。",
    "法人近5個交易日合計買超1576.69千張。",
    "外資近5個交易日合計買超1576.69千股。",
    "外資在9月18日單日買超965.04千股。",
    "法人在9月17日買超965.04千股。",
    "法人近30個交易日買超1576.69千股。",
    "法人近5個交易日買超1576.69股。",
    "法人2025年9月18日買超965.04千股。",
])
def test_real_and_semantic_corruption_is_rejected_even_for_neutral(agent, claim, data):
    assert short_term_evidence_issues(agent, "交易方向Neutral。" + claim, data)


@pytest.mark.parametrize("claim", [
    "法人近5個交易日合計買超1576.69千股。",
    "法人近5個交易日合計買超1576.69張。",
    "法人近5個交易日合計買超1.57669千張。",
    "法人2026年9月18日買超965.04千股。",
    "法人9月18日單日買超965.04張。",
    "法人9月15日賣超64.98千股。",
    "法人9月15日淨買超-64.98千股。",
    "投信近30個交易日買賣超0股。",
    "外資近30個交易日買超1528577股。",
    "自營商近30個交易日買超70.67千股。",
    "若外資近5日買超1576.69千張，才考慮進場。",
])
def test_correct_units_entity_period_and_conditional_claims(data, claim):
    assert short_term_evidence_issues(23, claim, data) == []


def test_null_does_not_become_zero(data):
    data['institutional_trading']['net_buy_shares_by_category']['investment_trust'] = None
    data['institutional_trading']['net_buy_thousand_shares_by_category']['investment_trust'] = None
    assert short_term_evidence_issues(23, '投信近30個交易日買賣超0股。', data)


def test_unknown_market_cannot_assume_lot_conversion(data):
    data['ticker'] = 'UNKNOWN'
    assert short_term_evidence_issues(23, '法人近5日買超1576.69張。', data)


def test_trade_catalog_scope_and_allowed_refs(data):
    from institutional_evidence import institutional_evidence_records, institutional_evidence_issues
    records = institutional_evidence_records(data)
    context = {'ticker': data['ticker'], 'short_term_market_context': {'institutional_evidence': {'records': records}}}
    path = 'short_term_market_context.institutional_evidence.records'
    i = next(i for i,r in enumerate(records) if r['path'].endswith('last_5_trading_days_net_buy_thousand_shares'))
    claim = '法人近5日買超1576.69千股。'
    assert institutional_evidence_issues(claim, context, allowed_paths=[f'{path}[{i}]']) == []
    assert institutional_evidence_issues(claim, context, allowed_paths=[]) != []
    j = next(i for i,r in enumerate(records) if r['population']=='foreign')
    assert institutional_evidence_issues(claim, context, allowed_paths=[f'{path}[{j}]']) != []
    copied=copy.deepcopy(context);copied['short_term_market_context']['institutional_evidence']['records'][i]['unit']=None
    assert institutional_evidence_issues(claim, copied, allowed_paths=[f'{path}[{i}]']) != []


@pytest.mark.parametrize('claim', [
    '截至2026年9月18日，法人近5日買超1576.69千股。',
    '法人近5日買超1576.69千股（截至2026年9月18日）。',
    '外資與投信近30日合計買超0股。',
    '法人9月16日至9月18日合計買超965.04千股。',
])
def test_as_of_range_and_combined_population_do_not_borrow_matching_values(data, claim):
    assert short_term_evidence_issues(23, claim, data)


def test_matching_as_of_and_separate_population_clauses_are_valid(data):
    assert short_term_evidence_issues(23, '截至2026年9月21日，法人近5日買超1576.69千股。', data) == []
    assert short_term_evidence_issues(23, '外資近30日買超1528577股，投信近30日買賣超0股。', data) == []


def test_date_only_citation_cannot_supply_amount(data):
    from institutional_evidence import institutional_evidence_records, institutional_evidence_issues
    rows = institutional_evidence_records(data)
    i = next(i for i,r in enumerate(rows) if r['window']=={'kind':'trailing_trading_days','trading_days':5})
    assert institutional_evidence_issues('法人近5日買超1576.69千股。', data,
        allowed_paths=[f'short_term_market_context.institutional_evidence.records[{i}].observed_at'])


def test_wrapped_catalog_retains_taiwan_lot_identity(data):
    from institutional_evidence import institutional_evidence_records, institutional_evidence_issues
    wrapped = {'short_term_market_context': {'ticker': '2033.TW',
        'institutional_evidence': {'records': institutional_evidence_records(data)}}}
    assert institutional_evidence_issues('法人近5日買超1576.69張。', wrapped) == []


@pytest.mark.parametrize('field,value', [('population', {}), ('unit', {}), ('value', None),
    ('value', float('nan')), ('provider', ''), ('observed_at', 'bad-date'), ('window', None)])
def test_malformed_records_are_unverifiable_without_aborting(data, field, value):
    from institutional_evidence import institutional_evidence_records, institutional_evidence_issues
    row = next(r for r in institutional_evidence_records(data) if r['path'].endswith('last_5_trading_days_net_buy_thousand_shares'))
    row[field] = value
    wrapped = {'ticker': '2033.TW', 'institutional_evidence': {'records': [row]}}
    assert institutional_evidence_issues('法人近5日買超1576.69千股。', wrapped)


def test_malformed_record_does_not_shift_cited_record_index(data):
    from institutional_evidence import institutional_evidence_records, institutional_evidence_issues
    row = next(r for r in institutional_evidence_records(data) if r['path'].endswith('last_5_trading_days_net_buy_thousand_shares'))
    wrapped = {'ticker': '2033.TW', 'institutional_evidence': {'records': [None, row]}}
    assert institutional_evidence_issues('法人近5日買超1576.69千股。', wrapped,
        allowed_paths=['short_term_market_context.institutional_evidence.records[0]'])


def test_existing_3105_gates_distinguish_waiting_from_orders_and_reject_unavailable_dcf():
    from final_audit_mode_contracts import v2_position_plan_contract_issues
    from final_audit_dcf import dcf_audit_findings
    plan = {'action': '等待', 'entry_zone': '資料不足，等待可驗證進場條件', 'position_size': '0%',
        'stop_loss': '資料不足，暫不建立部位', 'risk_reward': '資料不足',
        'invalidation_condition': '待股價拉回至 380-395 元歷史河流圖 31.3x-40x 區間且外資賣壓鈍化，或單月營收突破 20 億元確認基本面爆發後重新評估進場條件'}
    assert v2_position_plan_contract_issues(plan) == []
    assert v2_position_plan_contract_issues({**plan, 'entry_zone': plan['entry_zone'] + '，確認後買入10張'})
    rows = [{'scenario': scenario, 'method': 'fcf_dcf', 'unit': 'twd_per_share', 'intrinsic_value': value}
            for scenario, value in [('bear', 311), ('base', 520), ('bull', 645)]]
    quant = {'contract_version': 'quant_metrics.v2', 'metric_status': {
        'dcf': {'status': 'unavailable', 'reason_codes': ['dcf_non_positive_or_invalid_equity_value']}}}
    findings = dcf_audit_findings({14: 'DCF 情境'}, {'quant_metrics': quant}, {14: {'dcf_scenarios': rows}}, valuation_agent=14)
    assert {r['scenario'] for r in findings if r['severity']=='critical' and r['code']=='dcf_unavailable_claim'} == {'bear','base','bull'}
