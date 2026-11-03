"""Offline native-process-boundary replay; no new external acquisition."""
from pathlib import Path
from datetime import datetime
import json,sys
import pytest,time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'tests')]
from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements

@pytest.mark.parametrize('second_index_timeout',[False,True])
def test_native_json_audit_retains_each_current_http_observation(monkeypatch,second_index_timeout):
    from data_fetch.market_sources import twse_history_transport as transport
    from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
    fixture=json.loads((ROOT/'tests/fixtures/source_acquisition/mops_ordinary_originals_20261012.json').read_text())['issuers']['6924.TW']
    now=datetime.fromisoformat('2026-10-12T04:58:00+08:00')
    monkeypatch.setattr(time,'time',lambda:now.timestamp())
    for name in transport.PROXY_ENV:monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:{})
    def collect(argv,end,**kwargs):
        url,payload=argv[2],json.loads(argv[3])
        if second_index_timeout and url==transport.JSON_URL and payload['month']=='10':
            return {'body':b'','headers':b'','metadata':b'','process_started':True},-9,'timeout'
        data=(fixture['indexes'][str(int(payload['month']))]if url==transport.JSON_URL else
              fixture['originals'][json.dumps(payload,sort_keys=True)])
        raw=json.dumps(data,ensure_ascii=False).encode()
        return {'body':raw,'headers':b'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n',
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0}).encode(),
                'process_started':True},0,None
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    rows,audit=fetch_recent_company_announcements('6924.TW',now=now)
    if second_index_timeout:
        assert rows==[] and audit['status']=='error' and audit['http_status']is None
        assert audit['http_request_count']==len(audit['request_observations'])==2
        assert audit['request_observations'][0]['http_status']==200
        failed=audit['request_observations'][1]
        assert failed['http_status']is None and failed['http_status_observed']is False
        assert failed['response_bytes']==0 and failed['response_complete']is False
        return
    assert len(rows)==2 and audit['status']=='success'
    assert audit['http_request_count']==4
    observations=audit.get('request_observations',[])
    assert len(observations)==4, 'Native JSON branch drops its actual per-request transport observations'
    assert all(x['http_status_observed']and x['response_complete']and x['response_bytes']>0 for x in observations)
    import shared_provider_cache
    import asyncio
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    from data_fetch.types import FetchRequest
    from data_fetch.service import StockDataService
    from data_fetch.provider_registry import ProviderRegistry
    from test_report_refresh_acquisition_audit import init_db,events
    init_db()
    service=StockDataService(registry=ProviderRegistry([TwseCompanyHistoryProvider()]))
    context={'data':{'ticker':'6924.TW','instrument_type':'EQUITY','company_identity':{'official_name':'榮惠-KY創'}}}
    for cached in (False,True):
        monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:((rows,audit),{'cache_hit':cached,'stale':False,'fetched_at_epoch':time.time()}))
        result=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('6924.TW'),'official_announcements',context=context))
        assert len(result.data['recent_catalysts'])==2
        current=result.source_audit[0]
        assert current['status']==('skipped_fresh_cache'if cached else'success')
        assert current['http_request_sent']is (not cached)
        assert current['http_request_count']==(0 if cached else 4)
        assert current['request_observations']==([]if cached else observations)
    saved=events()
    assert len(saved)==2
    cold_details=json.loads(saved[0]['details_json']);warm_details=json.loads(saved[1]['details_json'])
    assert [x['url']for x in cold_details['request_observations']]==[x['url']for x in observations]
    assert warm_details['http_request_count']==0 and warm_details['request_observations']==[]
    from provider_acquisition import get_provider_acquisition_summary
    summary=next(x for x in get_provider_acquisition_summary()['sources']if x['source']=='recent_catalysts')
    assert summary['fetch_attempts']==summary['fetched_count']==1


def test_injected_callbacks_do_not_become_native_transport_proof():
    from test_mops_json_company_history import originals,NOW
    get,post,_=originals()
    rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert len(rows)==2 and audit['status']=='success'
    assert 'request_observations'not in audit and 'http_request_count'not in audit


def test_tdr_native_process_observations_are_kept_with_originals(monkeypatch):
    from data_fetch.market_sources import twse_history_transport as transport
    from test_tdr_mops_history import _source,NOW,PDF
    get,post,_=_source(monkeypatch)
    for name in transport.PROXY_ENV:monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:{})
    def collect(argv,end,**kwargs):
        if argv[0].endswith('curl'):
            url=argv[-1];response=get(url);mime='application/pdf'if url==PDF else'application/json'
        else:
            url=argv[2];response=post(url,json=json.loads(argv[3]));mime='application/json'
        return {'body':response.content,'headers':f'HTTP/2 200\r\nContent-Type: {mime}\r\n\r\n'.encode(),
                'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0}).encode(),
                'process_started':True},0,None
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    rows,audit=fetch_recent_company_announcements('9103.TW',now=NOW)
    assert len(rows)==2 and audit['status']=='success'
    assert audit['http_request_count']==len(audit['request_observations'])==5
    assert all(x['http_request_sent']and x['http_status_observed']and x['response_complete']for x in audit['request_observations'])
