import re
import pytest
import evidence_exit_gate as gate


@pytest.mark.parametrize('markers', [
    ('support',), ('support', 'resistance'), ('close','high','low'),
    ('support','resistance','close','high'), ('revenue',),
    ('support','sales'), ('support','monthly_revenue','revenue'),
])
def test_literal_fast_path_preserves_original_candidate_order_and_semantics(monkeypatch, markers):
    paths=['data.support','data.resistance','data.price_history[2026-10-01].close',
           'data.daily_market_data.high','data.daily_market_data.low',
           'data.financials.revenue_ttm_raw','data.institutional_trading.sales',
           'data.financials.net_sales','data.recent_monthly_revenue.year',
           'rerun_context.parsed.support']
    values=gate._InvocationValues()
    values.extend({'path':path,'value':float(index+1)} for index,path in enumerate(paths))
    normalized=[gate._normalize_match_text(path) for path in paths]
    monkeypatch.setattr(gate,'_path_markers_for_claim',lambda claim: markers)
    special=[m for m in markers if m in {'revenue','monthly_revenue','sales'}]
    simple=[gate._normalize_match_text(m) for m in markers if m not in special]
    pattern=re.compile('|'.join(re.escape(m) for m in simple)) if simple else None
    matched=[item for item,path in zip(values,normalized)
             if pattern is not None and pattern.search(path) or
                any(gate._normalize_match_text(m) in path and gate._semantic_marker_matches(item['path'],m) for m in special)]
    claim={'label':'amount','reported_value':1,'unit':''}
    expected=[gate._convert_snapshot_value_for_claim(claim,item,markers) for item in matched]
    actual=gate._relevant_snapshot_values(claim,values,normalized_paths=normalized)
    assert actual==expected
    assert gate._relevant_snapshot_values(claim,values,normalized_paths=normalized)==expected


def test_eligibility_is_evaluated_once_per_path_and_report(monkeypatch):
    original=gate._is_eligible_snapshot_value
    calls=[]
    def counted(item, **kwargs):
        calls.append(item['path'])
        return original(item, **kwargs)
    monkeypatch.setattr(gate,'_is_eligible_snapshot_value',counted)
    snapshot={'data':{'current_price':10,'support':'8, 9, 10','metadata':{'year':2025}}}
    gate.evaluate_report_evidence('Current price: 10 TWD',snapshot)
    assert calls.count('data.support')==1
    assert calls.count('data.metadata.year')==1
    assert len(calls)==len(set(calls))
    calls.clear()
    gate.evaluate_report_evidence('Current price: 10 TWD',snapshot)
    assert calls.count('data.support')==1
