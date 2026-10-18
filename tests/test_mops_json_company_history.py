"""Native saved ordinary issuer originals must survive publication-date updates."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json

import httpx
import pytest

from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
from source_content_selection import select_company_records
from news_freshness_policy import apply_news_freshness

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/mops_ordinary_originals_20261012.json'
FIXTURE_2838 = Path(__file__).parent / 'fixtures/source_acquisition/mops_ordinary_originals_2838_20261017.json'
NOW = datetime.fromisoformat('2026-10-12T04:58:00+08:00')
INDEX = 'https://mops.twse.com.tw/mops/api/t05st01'
DETAIL = 'https://mops.twse.com.tw/mops/api/t05st01_detail'


def originals(ticker='6924.TW', change=None):
    fixture = FIXTURE_2838 if ticker == '2838.TW' else FIXTURE
    payload = deepcopy(json.loads(fixture.read_text())['issuers'][ticker])
    if change:
        change(payload)
    calls = []
    def get(url, **kwargs):
        calls.append(('GET',url))
        return httpx.Response(500,request=httpx.Request('GET',url),json={})
    def post(url, **kwargs):
        calls.append(('POST',url,kwargs))
        if url==INDEX:
            response=payload['indexes'][str(int(kwargs['json']['month']))]
        elif url==DETAIL:
            response=payload['originals'][json.dumps(kwargs['json'],sort_keys=True)]
        else:
            response={'status':'success','data':[]}
        return httpx.Response(200,request=httpx.Request('POST',url),json=response)
    return get,post,calls


def test_checked_supplementary_original_uses_published_action_and_publication_date():
    get,post,calls=originals()
    rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert len(rows)==2, audit
    assert audit['status']=='success'and audit['coverage_status']=='window_complete'
    changed=next(r for r in rows if '補充公告' in r['title'])
    assert changed['date']=='2026-10-08T14:48:37+08:00'
    assert changed['source_request_parameters']['enterDate']=='1151007'
    assert changed['source_document_url']==DETAIL
    assert not any(c[0]=='GET'for c in calls)
    data={'ticker':'6924.TW','company_name':'榮惠-KY創','company_identity':{'official_name':'榮惠-KY創'},'instrument_type':'EQUITY'}
    selected,_=select_company_records(rows,data,cutoff=NOW)
    assert len(selected)==2
    apply_news_freshness(data,records=rows,cutoff=NOW)
    assert len(data['recent_catalysts'])==2
    assert data['news_selection']['publisher_count']==1


def test_source_component_refresh_keeps_conclusions_and_original_core_age(tmp_path):
    import asyncio,time
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db,events
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.types import ProviderResult
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    init_db()
    storage=InMemoryStorage();name,keys,snapshot=saved_report(storage)
    old=deepcopy(snapshot);old['ticker']=old['data']['ticker']='6924.TW'
    old['data']['company_name']='榮惠-KY創';old['data']['company_identity']={'official_name':'榮惠-KY創'};old['data']['instrument_type']='EQUITY'
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    get,post,_=originals();rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    calls=[]
    def fetch(request,context):
        calls.append(request.ticker)
        receipt={**audit,'source':'recent_catalysts','provider':'TWSE company announcement history',
                 'fetched_at_epoch':time.time(),'http_request_sent':True,'http_request_count':4,'event_kind':'aggregate'}
        return ProviderResult('recent_catalysts',receipt['provider'],audit['status'],value=rows,audit=receipt)
    def forbidden(*args):pytest.fail('must not acquire other sources or models')
    service=StockDataService(registry=ProviderRegistry([
        CallableProvider('recent_catalysts','TWSE company announcement history',fetch),
        CallableProvider('market_data','forbidden core',forbidden)]))
    response=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='official_announcements',return_refreshed_data=True))
    changed=json.loads(storage.get_report(keys.data_key).content)
    assert calls==['6924.TW']and len(changed['data']['recent_catalysts'])==2
    assert changed['data']['news_selection']['publisher_count']==1
    for key in ('current_price','revenue_history','years','earnings_call','peer_discovery_results'):
        assert changed['data'][key]==old['data'][key]
    assert changed['analysis_evidence']==old['analysis_evidence']
    for key in ('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
        assert changed[key]==old[key]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert response['analysis_text_stale']is True
    assert len(events())==1 and events()[0]['source']=='recent_catalysts'


@pytest.mark.parametrize('bad_identity',[False, [], 0, ''])
def test_explicit_malformed_identity_cannot_use_primary_issuer_text(bad_identity):
    get,post,_=originals();rows,_=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    accepted,_=select_company_records(rows,{'ticker':'6924.TW','company_identity':bad_identity},cutoff=NOW)
    assert accepted==[]


def test_forbidden_alias_keeps_html_and_star_normalization():
    get,post,_=originals();rows,_=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    data={'ticker':'6924.TW','company_identity':{'official_name':'榮惠-KY創','forbidden_aliases':['<b>* 榮惠-KY創 *</b>']}}
    accepted,_=select_company_records(rows,data,cutoff=NOW)
    assert accepted==[]


@pytest.mark.parametrize('ticker,count',[('2442.TW',2),('2838.TW',2),('2845.TW',1),('6550.TW',2),('6924.TW',2)])
def test_native_complete_originals_and_empty_sibling_months(ticker,count):
    get,post,calls=originals(ticker)
    rows,audit=fetch_recent_company_announcements(ticker,now=NOW,get=get,post=post)
    assert len(rows)==count and audit['status']=='success'and audit['coverage_status']=='window_complete'
    assert sum(c[1]==INDEX for c in calls)==2 and sum(c[1]==DETAIL for c in calls)==count
    assert not any(c[0]=='GET'for c in calls)
    accepted,_=select_company_records(rows,{'ticker':ticker},cutoff=NOW)
    assert len(accepted)==count


@pytest.mark.parametrize('field',['text','publisher','source_request_parameters','date','mops_json_receipt'])
def test_saved_record_changes_cannot_be_reauthenticated_with_recomputed_content_hash(field):
    from hashlib import sha256
    get,post,_=originals();rows,_=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    row=deepcopy(rows[0])
    if field=='text':row['text']+='\n未經原文核對的新主張';row['summary']=row['text'][:1500];row['content_sha256']=sha256(row['text'].encode()).hexdigest()
    elif field=='publisher':row[field]='另一家獨立媒體'
    elif field=='source_request_parameters':row[field]['enterDate']='1151008'
    elif field=='date':row[field]='2026-10-09T14:48:37+08:00'
    else:row.pop(field)
    accepted,_=select_company_records([row],{'ticker':'6924.TW'},cutoff=NOW)
    assert accepted==[]


@pytest.mark.parametrize('status',[403,429,503])
def test_refused_original_stops_without_old_html_or_next_original(status):
    get,original_post,calls=originals();refused=[]
    def post(url,**kwargs):
        if url==DETAIL:
            refused.append(kwargs['json'])
            return httpx.Response(status,request=httpx.Request('POST',url),headers={'Retry-After':'3600'})
        return original_post(url,**kwargs)
    rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert rows==[]and audit['status']=='error'and audit['http_status']==status
    assert len(refused)==1 and not any(c[0]=='GET'for c in calls)


def test_complete_empty_indexes_do_not_manufacture_records_or_success():
    get,original_post,calls=originals()
    def post(url,**kwargs):
        calls.append(('POST',url,kwargs))
        assert url==INDEX
        return httpx.Response(200,request=httpx.Request('POST',url),json={'code':406,'message':'查無相符資料','result':None})
    rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert rows==[]and audit['status']!='success'and len(calls)==2


def test_original_finished_after_shared_deadline_cannot_count_success(monkeypatch):
    from data_fetch.market_sources import mops_json_company_history as source
    clock=[100.];monkeypatch.setattr(source.time,'monotonic',lambda:clock[0])
    get,post,_=originals();parse=source._record
    def late(*args):
        row=parse(*args);clock[0]=121.;return row
    monkeypatch.setattr(source,'_record',late)
    rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert rows==[]and audit['status']!='success'and audit['coverage_status']=='partial'


def test_missing_original_bytes_fail_closed(tmp_path):
    get,post,_=originals();rows,_=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    path=Path(rows[0]['mops_json_receipt']['detail_receipt']['raw_response_path']);path.unlink()
    accepted,_=select_company_records([rows[0]],{'ticker':'6924.TW'},cutoff=NOW)
    assert accepted==[]


def test_prompt_projection_excludes_new_receipt_paths_and_keeps_content():
    from prompt_evidence import prompt_evidence_copy
    get,post,_=originals();rows,_=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    projected=prompt_evidence_copy({'recent_catalysts':rows})
    assert 'mops_json_receipt' not in projected['recent_catalysts'][0]
    assert projected['recent_catalysts'][0]['text']==rows[0]['text']
    assert 'raw_response_path'not in json.dumps(projected)


def test_conflicting_identity_instrument_type_is_locally_blocked_before_provider():
    import asyncio
    from data_fetch import FetchRequest
    from data_fetch.service import StockDataService
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    def forbidden(*args):pytest.fail('contradictory ETF identity must be rejected before provider')
    service=StockDataService(registry=ProviderRegistry([
        CallableProvider('recent_catalysts','TWSE company announcement history',forbidden)]))
    with pytest.raises(RuntimeError):
        asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('6924.TW'), 'official_announcements',
            context={'data':{'ticker':'6924.TW','instrument_type':'EQUITY','company_identity':{'instrument_type':'ETF'}}}))


def test_damaged_provider_output_is_failed_before_success_ledger():
    import asyncio,time
    from data_fetch import FetchRequest
    from data_fetch.service import StockDataService
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import ProviderResult
    from test_report_refresh_acquisition_audit import init_db,events
    init_db();get,post,_=originals();rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    rows[0]['text']+='\n伪造的新主張'
    def fetch(request,context):
        receipt={**audit,'source':'recent_catalysts','provider':'TWSE company announcement history','fetched_at_epoch':time.time()}
        return ProviderResult('recent_catalysts',receipt['provider'],'success',value=rows,audit=receipt)
    service=StockDataService(registry=ProviderRegistry([CallableProvider('recent_catalysts','TWSE company announcement history',fetch)]))
    response=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('6924.TW'),'official_announcements',context={'data':{'ticker':'6924.TW'}}))
    assert response.data['recent_catalysts']==[]
    assert len(events())==1 and events()[0]['status']=='error'and events()[0]['record_count']==0


def test_warm_provider_preserves_original_epoch_and_reports_http_zero(monkeypatch):
    from data_fetch import FetchRequest
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    get,post,_=originals();rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post);calls=[]
    def fetch(self,ticker):calls.append(ticker);return rows,audit
    monkeypatch.setattr(TwseCompanyHistoryProvider,'_fetch_records',fetch)
    provider=TwseCompanyHistoryProvider();request=FetchRequest.from_ticker('6924.TW')
    cold=provider.fetch(request);warm=provider.fetch(request)
    assert calls==['6924.TW']and cold.status=='success'and warm.status=='skipped_fresh_cache'
    assert warm.audit['http_request_sent']is False and warm.audit['http_request_count']==0
    assert warm.audit['fetched_at_epoch']==cold.audit['fetched_at_epoch']


def test_distinct_original_actions_with_same_title_are_not_one_event():
    def change(payload):
        title='公告本公司董事會重大決議事項'
        for month in payload['indexes'].values():
            for row in month['result']['data']:row[4]=title
        for detail in payload['originals'].values():detail['result']['data'][0][6]=title
    get,post,_=originals(change=change)
    rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert len(rows)==2 and audit['status']=='success'
    data={'ticker':'6924.TW'};apply_news_freshness(data,records=rows,cutoff=NOW)
    assert len(data['recent_catalysts'])==2


@pytest.mark.parametrize('same_title',[False,True])
def test_verified_event_identity_survives_original_eight_three_quality_gate(monkeypatch,same_title):
    from datetime import timedelta
    from data_fetch import catalyst_search_plan as plan
    from data_fetch.types import ProviderResult
    def change(payload):
        row=deepcopy(payload['indexes']['10']['result']['data'][0])
        original_key=json.dumps(row[5]['parameters'],sort_keys=True)
        detail=deepcopy(payload['originals'][original_key])
        row[2]='115/10/09';row[3]='09:00:00';row[4]='榮惠-KY創公告本公司另一項董事會重大決議'
        row[5]['parameters'].update(enterDate='1151009',serialNumber='2')
        detail['result']['data'][0][0]='2';detail['result']['data'][0][1]=row[2];detail['result']['data'][0][2]=row[3];detail['result']['data'][0][6]=row[4]
        payload['indexes']['10']['result']['data'].append(row)
        payload['originals'][json.dumps(row[5]['parameters'],sort_keys=True)]=detail
        if same_title:
            for index in payload['indexes'].values():
                for item in index['result']['data']:item[4]='榮惠-KY創公告本公司董事會重大決議事項'
            for item in payload['originals'].values():item['result']['data'][0][6]='榮惠-KY創公告本公司董事會重大決議事項'
    get,post,_=originals(change=change);rows,audit=fetch_recent_company_announcements('6924.TW',now=NOW,get=get,post=post)
    assert len(rows)==3 and audit['status']=='success'
    news=[{'date':(NOW-timedelta(hours=2)).isoformat(),'title':f'榮惠-KY創營運新聞{i}',
           'summary':'榮惠-KY創公布本公司營運及投資資料','link':f'https://news{i%2}.example/article/{i}','source':f'Publisher{i%2}'}for i in range(5)]
    monkeypatch.setattr(plan,'news_cutoff',lambda:NOW)
    evidence=plan.current_catalyst_evidence({'ticker':'6924.TW','company_name':'榮惠-KY創'},[
        ProviderResult('recent_catalysts','Free news waterfall','success',value=news,audit={'selection_policy':'company-time-v1','quality_status':'eligible_evidence'}),
        ProviderResult('recent_catalysts','TWSE company announcement history','success',value=rows,audit=audit)])
    assert evidence['eligible_count']==8 and evidence['publisher_count']==3 and evidence['sufficient']is True
    assert all(r['link']=='https://mops.twse.com.tw/mops/#/web/t05st01' for r in evidence['record_refs'] if r['publisher']=='臺灣證券交易所／公開資訊觀測站')
