"""Already parsed official OpenAPI data needs exact issuer/raw proof before citations."""
from copy import deepcopy
from datetime import datetime,timezone
import json
import pytest
from test_tpex_openapi_institutional import ROW

@pytest.fixture
def data(monkeypatch,tmp_path):
    import runtime_paths
    from official_response_evidence import archive_response
    from tpex_openapi_institutional import SOURCE,URL,parse_latest_report
    from institutional_observations import summarize_observations
    paths=runtime_paths.RuntimePaths.from_values(cache_dir=tmp_path,output_dir=tmp_path/'output')
    monkeypatch.setattr(runtime_paths,'current_runtime_paths',lambda:paths)
    raw=json.dumps([ROW]).encode();parsed=parse_latest_report(raw,'2026-10-08');row=parsed['rows']['5314']
    proof=archive_response(raw,source_url=URL,retrieved_at='2026-10-08T15:00:00+00:00',http_status=200)
    records=[{'date':'2026-10-08','category':cat,'net_buy_shares':row[cat],'source':SOURCE,'source_url':URL,'unit':'shares'}
             for cat in ('foreign','investment_trust','dealer')]
    value=summarize_observations(records,'5314.TWO',limit=1)
    value['latest_official_observation']={'ticker':'5314.TWO','date':'2026-10-08','market':'TPEX','raw_evidence':proof}
    return {'ticker':'5314.TWO','institutional_trading':value}


def test_exact_public_raw_proof_enables_snapshot_citations_with_pit_still_false(data):
    from report_source_admission import institutional_admission
    from institutional_evidence import institutional_evidence_records
    from institutional_daily_evidence import daily_category_records
    value=data['institutional_trading']
    admission=institutional_admission(value,'2026-10-08')
    assert admission['eligible'] and admission['historical_point_in_time_verified'] is False
    rows=institutional_evidence_records(data)
    daily=[r for r in rows if r['path'].startswith('institutional_trading.daily_category_observations[')]
    assert len(daily)==3 and {r['population']for r in daily}=={'foreign','investment_trust','dealer'}
    # A source label alone is not authority; the enclosing issuer is required.
    assert daily_category_records(value)==[]

@pytest.mark.parametrize('mutate',[
    lambda d:d.update(ticker='2330.TWO'),
    lambda d:d.update(ticker='5314.TW'),
    lambda d:d['institutional_trading'].pop('latest_official_observation'),
    lambda d:d['institutional_trading']['latest_official_observation']['raw_evidence'].update(source_url='https://example.invalid/api'),
    lambda d:d['institutional_trading']['daily_category_observations'][0].update(net_buy_shares=999),
    lambda d:d['institutional_trading']['net_buy_shares_by_category'].update(foreign=999),
    lambda d:d['institutional_trading'].update(total_net_buy_thousand_shares=999),
    lambda d:d['institutional_trading'].update(observation_dates=[[]]),
    lambda d:d['institutional_trading'].update(last_5_trading_days_net_buy_thousand_shares=999),
    lambda d:d['institutional_trading']['daily_total_net_buy_last_10'][0].update(net_buy_thousand_shares=999),
    lambda d:d['institutional_trading']['daily_category_observations'][0].update(category=[]),
    lambda d:d['institutional_trading']['daily_category_observations'][0].update(net_buy_shares=10**1000),
])
def test_label_and_wrong_issuer_endpoint_or_values_never_enable_citations(data,mutate):
    from institutional_evidence import institutional_evidence_records
    mutate(data)
    assert institutional_evidence_records(data)==[]
