from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import asyncio,json,time
import pytest

NOW=datetime(2026,10,10,5,10,tzinfo=ZoneInfo('Asia/Taipei'))


@pytest.fixture(autouse=True)
def cache_isolation():
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    yield
    cache_store.reset_cache_store_for_tests()


def payload():
    return {'stat':'OK','title':'公布注意有價證券資訊 (115年09月10日 至 115年10月10日 個股)',
            'fields':['編號','證券代號','證券名稱','累計次數','注意交易資訊','日期','收盤價','本益比'],
            'params':{'startDate':'20260910','endDate':'20261010','stockNo':'9103','querytype':'2','sortKind':'DATE','response':'json','controller':'announcement','action':'notice','lang':'zh','selectType':''},
            'count':1,'total':2,'data':[[1,'9103','美德醫療-DR','1','臺灣存託憑證兩地收盤價溢價82.59 % ﹝第八款﹞。','115.10.08','5.88','-----'],[2,'9103','美德醫療-DR','1','臺灣存託憑證兩地收盤價溢價72.20 % ﹝第八款﹞。','115.10.07','5.35','-----']]}


def collected(body=None):
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices
    body=json.dumps(payload() if body is None else body,ensure_ascii=False).encode()
    def get(url):return body
    return fetch_trading_notices('9103.TW',now=NOW,get=get)


def test_current_official_notice_records_are_complete_dated_and_revalidated():
    from data_fetch.market_sources.twse_trading_notices import verified_notice_record
    rows,audit=collected()
    assert audit['status']=='success' and audit['record_count']==2
    assert len({r['link'] for r in rows})==2
    assert rows[0]['date']=='2026-10-08' and rows[0]['publication_date_precision']=='day'
    assert '82.59 %' in rows[0]['text'] and rows[0]['content_truncated'] is False
    assert verified_notice_record(rows[0],{'ticker':'9103.TW'})=='9103'
    assert 'current_price' not in rows[0] and 'sentiment_score' not in rows[0]


@pytest.mark.parametrize('change',['issuer','name','period','future','duplicate_day','fields','query','total_bool','count_mismatch','wrong_title'])
def test_wrong_source_identity_or_incomplete_envelope_does_not_produce_records(change):
    p=payload()
    if change=='issuer':p['data'][0][1]='2330'
    elif change=='name':p['data'][0][2]=''
    elif change=='period':p['data'][0][5]='115.09.09'
    elif change=='future':p['data'][0][5]='115.10.11'
    elif change=='duplicate_day':p['data'][1][5]=p['data'][0][5]
    elif change=='fields':p['fields'][4]='摘要'
    elif change=='query':p['params']['stockNo']='2330'
    elif change=='total_bool':p['total']=True
    elif change=='count_mismatch':p['count']=2
    else:p['title']='Security verification'
    rows,audit=collected(p)
    assert rows==[] and audit['status']!='success'


@pytest.mark.parametrize('field,value',[('text','美德醫療-DR（9103）fake'),('date','2026-10-09'),('publication_date_precision','second'),('content_truncated',0),('link','https://evil.test/'),('source_type','news')])
def test_tampered_saved_notice_cannot_fall_through_generic_company_matching(field,value):
    from source_content_selection import issuer_match
    rows,_=collected();r=deepcopy(rows[0]);r[field]=value
    assert issuer_match(r,{'ticker':'9103.TW','company_name':'美德醫療-DR'}) is None


def test_missing_original_receipt_is_not_generic_issuer_evidence():
    from source_content_selection import issuer_match
    rows,_=collected();r=deepcopy(rows[0]);r.pop('trading_notice_receipt')
    assert issuer_match(r,{'ticker':'9103.TW','company_name':'美德醫療-DR'}) is None


def test_model_projection_keeps_notice_facts_and_link_without_internal_receipt():
    from prompt_evidence import prompt_evidence_copy
    rows,_=collected();original=deepcopy(rows)
    public=prompt_evidence_copy(rows)
    for saved,projected in zip(rows,public):
        assert 'trading_notice_receipt' not in projected
        for field in ('title','text','summary','date','link','source','source_type','publication_date_precision'):
            assert projected[field]==saved[field]
    assert rows==original and 'trading_notice_receipt' in rows[0]


def test_public_model_formatter_omits_notice_archive_paths_and_keeps_citations():
    from prompt_builder import format_data_for_prompt
    rows,_=collected();data={'ticker':'9103.TW','company_name':'美德醫療-DR','recent_catalysts':rows}
    before=deepcopy(data);text=format_data_for_prompt(data)
    payload,_=json.JSONDecoder().raw_decode(text[text.index('{'):]);actual=payload['market_catalysts']['items']
    assert len(actual)==2 and all('trading_notice_receipt' not in r for r in actual)
    assert [r['text'] for r in actual]==[r['text'] for r in rows]
    assert [r['link'] for r in actual]==[r['link'] for r in rows]
    assert data==before


def test_valid_empty_does_not_become_nonempty_success():
    p=payload();p.update(data=[],count=0,total=0)
    rows,audit=collected(p)
    assert rows==[] and audit['status']=='unavailable' and audit['record_count']==0


def test_unavailable_source_preserves_original_failure():
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices
    from search_provider_runtime import SourceResponseError
    def fail(url):raise SourceResponseError('rate_limited',status_code=429)
    rows,audit=fetch_trading_notices('9103.TW',now=NOW,get=fail)
    assert rows==[] and audit['status']=='error' and audit['error_kind']=='rate_limited' and audit['http_status']==429


def test_http_200_unverified_envelope_cannot_be_a_successful_raw_cache(monkeypatch):
    from hashlib import sha256
    import base64
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    from data_fetch.market_sources.twse_trading_notices import fetch_trading_notices
    calls=[]
    def bad(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1;diagnostic['http_request_sent']=True
        raw=b'{"stat":"Security verification"}'
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp,'_download',bad)
    first,audit=fetch_trading_notices('9103.TW');second,warm=fetch_trading_notices('9103.TW')
    assert first==second==[] and audit['status']==warm['status']=='error'
    assert len(calls)==1 and audit['http_request_sent'] is True and warm['http_request_sent'] is False
    assert audit['component_statuses']['official_notice']['raw_response_receipt']['status']=='archived'
    assert warm['cache_hit'] is False and warm['record_count']==0


def test_original_revalidation_cannot_overrun_the_collector_deadline(monkeypatch):
    import data_fetch.market_sources.twse_trading_notices as module
    clock=[0.];original=module.verified_notice_record
    def slow(*args):
        result=original(*args);clock[0]=9.;return result
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(module,'verified_notice_record',slow)
    rows,audit=collected()
    assert rows==[] and audit['status']=='error' and audit['error_kind']=='TimeoutError'


@pytest.mark.parametrize('requested,resolved',[('9103.TW','2330.TW'),('9103.TWO','9103.TW'),('AAPL','9103.TW'),('2330','9103.TW'),('9103','9103.TWO')])
def test_context_cannot_redirect_public_provider_to_another_issuer_or_market(monkeypatch,requested,resolved):
    from data_fetch.trading_notices_provider import TradingNoticesProvider
    from data_fetch.types import FetchRequest
    calls=[]
    def collect(ticker):calls.append(ticker);return [],{'status':'unavailable','record_count':0}
    monkeypatch.setattr('data_fetch.trading_notices_provider.fetch_trading_notices',collect)
    result=TradingNoticesProvider().fetch(FetchRequest.from_ticker(requested),{'data':{'ticker':resolved}})
    assert calls==[] and result.audit['http_request_sent'] is False and result.audit['record_count']==0
    assert result.audit['event_kind']=='local_block' and result.status!='success'


@pytest.mark.parametrize('change',['body','missing_archive','original_kind','wrong_row','row_bool'])
def test_saved_original_is_rechecked_at_selection(monkeypatch,change):
    from source_content_selection import issuer_match
    import data_fetch.market_sources.twse_trading_notices as module
    rows,_=collected();row=deepcopy(rows[0]);proof=row['trading_notice_receipt']
    if change=='body':monkeypatch.setattr(module,'read_response',lambda p:b'{}')
    elif change=='missing_archive':
        def unavailable(p):raise OSError('original missing')
        monkeypatch.setattr(module,'read_response',unavailable)
    elif change=='original_kind':proof['original']['evidence_kind']='decoded_sdk_projection'
    elif change=='wrong_row':proof['row_index']=1
    else:proof['row_index']=True
    assert issuer_match(row,{'ticker':'9103.TW','company_name':'美德醫療-DR'}) is None


@pytest.mark.parametrize('change',['host','port','fragment','route','duplicate_parameter','wrong_market','too_wide','future_invalid_date'])
def test_notice_transport_only_allows_one_fixed_official_issuer_query(change):
    from data_fetch.market_sources.trading_notice_transport import url_contract
    from search_provider_runtime import SourceResponseError
    from data_fetch.market_sources.twse_trading_notices import source_url
    url=source_url('9103.TW',NOW)
    if change=='host':url=url.replace('www.twse.com.tw','www.twse.com.tw.evil.test')
    elif change=='port':url=url.replace('www.twse.com.tw','www.twse.com.tw:443')
    elif change=='fragment':url+='#redirect'
    elif change=='route':url=url.replace('/announcement/notice','/other')
    elif change=='duplicate_parameter':url+='&stockNo=2330'
    elif change=='wrong_market':url=url.replace('stockNo=9103','stockNo=0050')
    elif change=='too_wide':url=url.replace('startDate=20260910','startDate=20260901')
    else:url=url.replace('endDate=20261010','endDate=20261310')
    with pytest.raises(SourceResponseError):url_contract(url)


def test_public_provider_registry_keeps_market_and_quote_scope():
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import FetchRequest
    registry=ProviderRegistry();name='TWSE official trading notices'
    for ticker in ('9103.TW','3023.TW','2330'):
        assert name in registry.provider_names(FetchRequest.from_ticker(ticker),'recent_catalysts')
    for ticker in ('9103.TWO','AAPL','0050.TW'):
        assert name not in registry.provider_names(FetchRequest.from_ticker(ticker),'recent_catalysts')


def test_public_workflow_saves_notice_records_without_waiving_search_gate(monkeypatch):
    from data_fetch.provider_base import DataProvider
    from data_fetch.types import FetchRequest,ProviderResult
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.workflow import _run_optional_provider_plan
    calls=[]
    class Notice(DataProvider):
        name='TWSE official trading notices';source='recent_catalysts';markets={'tw'}
        def fetch(self,request,context=None):
            calls.append('notice');rows,audit=collected()
            return ProviderResult(self.source,self.name,'success',value=rows,audit=audit)
    class Search(DataProvider):
        name='Alternative Search';source='recent_catalysts';markets={'tw'}
        def fetch(self,request,context=None):
            calls.append('search')
            return ProviderResult(self.source,self.name,'unavailable',value=[],audit={'source':self.source,'provider':self.name,'status':'unavailable','record_count':0})
    monkeypatch.setattr('data_fetch.workflow.cache_financial_payload',lambda *a:None)
    # Import before patching the function so a lazy import cannot retain the
    # frozen fixture cutoff in another module after monkeypatch restoration.
    import data_fetch.catalyst_search_plan as plan
    monkeypatch.setattr(plan,'news_cutoff',lambda *a,**k:NOW)
    monkeypatch.setattr('news_freshness_policy.news_cutoff',lambda *a,**k:NOW)
    data={'ticker':'9103.TW','company_name':'美德醫療-DR','recent_catalysts':[]}
    result=asyncio.run(_run_optional_provider_plan(FetchRequest.from_ticker('9103.TW',record_provider_sla=False),ProviderRegistry([Notice(),Search()]),data,sources=('recent_catalysts',)))
    assert len(result['recent_catalysts'])==2 and calls==['notice','search']
