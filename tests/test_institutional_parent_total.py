"""A parent institution total must not inherit its parenthetical component."""
import pytest

from institutional_evidence import institutional_evidence_issues


def data():
    return {'ticker':'1623.TW','institutional_trading':{
        'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date':'2026-10-22','lookback_trading_days':30,
        'total_net_buy_shares':-205161,
        'net_buy_shares_by_category':{'foreign':-202840,'investment_trust':0,'dealer':-2321},
    }}


@pytest.mark.parametrize('text',[
    '近期法人籌碼連續賣超（近 30 交易日外資賣超 202.84 千股，合計賣超 205.16 千股）。',
    '近期三大法人籌碼連續賣超(近30交易日外資賣超202.84千股,合計賣超205.16千股)。',
    '近期法人籌碼連續賣超（近30交易日外資賣超202.84千股，總計賣超205.16千股）。',
])
def test_parenthetical_total_restores_explicit_parent_population(text):
    assert institutional_evidence_issues(text,data())==[]


@pytest.mark.parametrize('text',[
    '近30交易日外資賣超202.84千股，合計賣超205.16千股。',
    '外資籌碼連續賣超（近30交易日外資賣超202.84千股，合計賣超205.16千股）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，外資合計賣超205.16千股）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，合計賣超202.84千股）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，合計買超205.16千股）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，合計賣超205.16千張）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，近5交易日合計賣超205.16千股）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，投信賣超0千股，合計賣超205.16千股）。',
    '法人籌碼連續賣超。近30交易日外資賣超202.84千股，合計賣超205.16千股。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股），合計賣超205.16千股。',
    '法人籌碼連續賣超（近30交易日外資賣超205.16千股，合計賣超205.16千股）。',
])
def test_total_binding_does_not_relax_owner_window_units_or_numbers(text):
    assert institutional_evidence_issues(text,data())


def test_parent_total_requires_its_own_allowed_source():
    text = '法人籌碼連續賣超（近30交易日外資賣超202.84千股，合計賣超205.16千股）。'
    assert institutional_evidence_issues(text, data(), allowed_paths=[
        'institutional_trading.net_buy_shares_by_category.foreign',
    ])
    assert institutional_evidence_issues(text, data(), allowed_paths=[])


def test_parent_total_cannot_mix_component_and_total_observation_dates():
    from institutional_evidence import institutional_evidence_records
    records = institutional_evidence_records(data())
    records = [{**record, 'observed_at': '2026-10-21'}
               if record['population'] == 'foreign' else record for record in records]
    source = {'ticker': '1623.TW', 'institutional_evidence': {'records': records}}
    text = '法人籌碼連續賣超（近30交易日外資賣超202.84千股，合計賣超205.16千股）。'
    assert institutional_evidence_issues(text, source)


def test_parent_total_cannot_pick_one_date_from_ambiguous_component_evidence():
    from institutional_evidence import institutional_evidence_records
    records = institutional_evidence_records(data())
    older = [{**record, 'observed_at': '2026-10-21'}
             for record in records if record['population'] == 'foreign']
    source = {'ticker': '1623.TW', 'institutional_evidence': {'records': records + older}}
    text = '法人籌碼連續賣超（近30交易日外資賣超202.84千股，合計賣超205.16千股）。'
    assert institutional_evidence_issues(text, source)


@pytest.mark.parametrize('text', [
    '法人籌碼連續賣超（截至2026-10-21，近30交易日外資賣超202.84千股，合計賣超205.16千股）。',
    '法人籌碼連續賣超（近30交易日外資賣超202.84千股，2026-10-21合計賣超205.16千股）。',
])
def test_parent_total_retains_explicit_observation_date_checks(text):
    assert institutional_evidence_issues(text, data())
