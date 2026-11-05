from copy import deepcopy
from datetime import date
import pytest
from data_fetch.market_sources import peer_reference_transport as t,starair_reference_spec as s
from test_peer_reference_transport import parts,own


def test_old_common_spec_and_cache_identity_stays_identical():
    for kind,kwargs in [('home',{}),('methodology',{}),('reference',{'day':date(2026,11,3)})]:
        assert s.spec(kind,**kwargs)==t.spec(kind,**kwargs)
        assert t.raw_key(s.spec(kind,**kwargs))==t.raw_key(t.spec(kind,**kwargs))


def test_new_individual_request_has_one_explicit_canonical_subject(monkeypatch):
    request=s.spec('income',year=2026,quarter=2)
    assert t.canonical_spec(request)==request
    assert request['data']['companyId']=='2646 星宇航空'
    h=t.PeerIncomeHttp(peer_ticker='2646.TW')
    value=parts(request)
    packet=h._consume(request,request['url'],value,0,None,{})
    own(packet,request,monkeypatch)
    assert t.receipt_body(packet,request)==value['body']
    assert t.raw_key(request)!=t.raw_key(t.spec('income',year=2026,quarter=2))


@pytest.mark.parametrize('change',['ticker','company','method','URL','quarter','mime','marker_missing'])
def test_new_marker_never_licenses_changed_input(change):
    request=s.spec('income',year=2026,quarter=2)
    if change=='ticker':request['params'][s.MARKER]='6558.TW'
    elif change=='company':request['data']['companyId']='6230 尼得科超眾'
    elif change=='method':request['method']='GET'
    elif change=='URL':request['url']='https://evil.invalid/compare/report'
    elif change=='quarter':request['params']['quarter']=True
    elif change=='mime':request['mime']='application/json'
    else:del request['params'][s.MARKER]
    with pytest.raises(ValueError):t.canonical_spec(request)


def test_transport_cannot_cross_subject_even_with_valid_original_schema():
    request=s.spec('income',year=2026,quarter=2)
    with pytest.raises(ValueError):t.PeerIncomeHttp()._consume(request,request['url'],parts(request),0,None,{})
    old=t.spec('income',year=2026,quarter=2)
    with pytest.raises(ValueError):t.PeerIncomeHttp(peer_ticker='2646.TW')._consume(old,old['url'],parts(old),0,None,{})
    with pytest.raises(ValueError):t.PeerIncomeHttp(peer_ticker='6558.TW')


def test_passive_HTTP_subject_matches_actual_individual_consumer(monkeypatch):
    from provider_correlation import correlation_scope,source_operation
    from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
    import provider_sla
    entries=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:entries.extend(rows))
    request=s.spec('income',year=2026,quarter=2)
    with correlation_scope(replace=True,ticker='6757.TW',fetch_id='f'),source_operation('dynamic_peer_metrics','FinMind/yfinance'),receipt_observation_scope(True):
        h=t.PeerIncomeHttp(peer_ticker='2646.TW');h._consume(request,request['url'],parts(request),0,None,{})
    assert len(entries)==1 and entries[0]['peer_ticker']=='2646.TW'and entries[0]['ticker']=='6757.TW'
    assert entries[0]['record_count']==0
