"""Normal Taiwan enrichment retains the canonical peer diagnostics exactly once."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))

@pytest.mark.parametrize('ticker',['8926.TW','2330.TW','5314.TWO'])
def test_every_taiwan_peer_path_retains_rejection_diagnostics_without_extra_fetch(monkeypatch,ticker):
    from data_fetch import yfinance_sync_enrichment as sync
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.types import ProviderResult
    import source_applicability
    calls=[];legacy=[]
    def peer(self,request,context):
        calls.append(request.ticker)
        return ProviderResult(source='dynamic_peer_metrics',provider='FinMind/yfinance',status='degraded_enrichment',value=[],
            audit={'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','status':'degraded_enrichment',
                   'record_count':0,'coverage_status':'unavailable','selection_status':'target_undated_master_row',
                   'candidate_count':0,'identity_master':{'cache_hit':True,'http_request_count':0}})
    monkeypatch.setattr(DynamicPeerMetricsProvider,'fetch',peer)
    monkeypatch.setattr(source_applicability,'source_is_applicable',lambda source,*args:source=='dynamic_peer_metrics')
    def named(fetches,**kwargs):legacy.extend(fetches);return {'values':{},'audit':[]}
    monkeypatch.setattr(sync,'_run_named_fetches',named)
    result=sync.fetch_sync_enrichment_bundle(ticker=ticker,stock=object(),company_name=ticker,
        sector='Industrials',industry='Engineering & Construction',company_identity={'instrument_type':'EQUITY'},
        years=[],net_income_history=[],shares_outstanding=None,skip_optional_http=True)
    assert calls==[ticker]
    assert 'dynamic_peer_metrics'not in legacy
    audits=[r for r in result['audit']if r.get('source')=='dynamic_peer_metrics']
    assert len(audits)==1 and audits[0]['selection_status']=='target_undated_master_row'
    assert audits[0]['identity_master']['http_request_count']==0
    assert result['dynamic_peer_metrics']==[]
