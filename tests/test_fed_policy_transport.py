import sys
from pathlib import Path
import pytest
import fed_policy_transport as f
import provider_sla
from provider_correlation import correlation_scope,source_operation
from search_provider_runtime import SourceResponseError

def test_route_exact_and_bounded():
    assert f.PolicyHttp.route_contract(f.FEED_URL)[0]==1_000_000
    for url in [f.FEED_URL+'?other=1',f.FEED_URL.replace('https:','http:'),f.FEED_URL.replace('www.federalreserve.gov','evil.test')]:
        with pytest.raises(SourceResponseError):f.PolicyHttp.route_contract(url)

@pytest.mark.parametrize('cache,sent,error',[(False,True,None),(True,False,None),(False,True,429),(False,False,429)])
def test_http_and_cache_evidence_remain_distinct(monkeypatch,cache,sent,error):
    events=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda es:events.extend(es))
    class Http:
        def __init__(self,*a):self.components=[]
        def get(self,url):
            assert url==f.FEED_URL
            self.components.append({'cache_hit':cache,'http_request_sent':sent,'fetched_at_epoch':123})
            if error:raise SourceResponseError('rate_limited',status_code=error)
            return b'raw feed bytes'
    monkeypatch.setattr(f,'PolicyHttp',Http)
    with correlation_scope(replace=True,job_id='fed-test',ticker='2892.TW'):
        with source_operation('international_news_context','GDELT / Google News RSS'):
            if error:
                with pytest.raises(SourceResponseError):f.load_policy_feed()
            else:assert f.load_policy_feed()['cache_hit'] is cache
    assert len(events)==int(sent and not cache)
    for e in events:
        assert e['record_count']==0 and e['event_kind']=='http_transport_receipt'
        assert e['http_status']==(error or 200)
        assert e['status']==('error' if error else 'success')
        assert 'raw feed bytes' not in str(e)

def test_audit_failure_cannot_discard_feed(monkeypatch):
    def fail(*a):raise RuntimeError('audit unavailable')
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',fail)
    class Http:
        def __init__(self,*a):self.components=[{'cache_hit':False,'http_request_sent':True}]
        def get(self,url):return b'raw'
    monkeypatch.setattr(f,'PolicyHttp',Http)
    with correlation_scope(replace=True,ticker='2892.TW'):
        with source_operation('international_news_context','GDELT / Google News RSS'):
            assert f.load_policy_feed()['raw']==b'raw'
