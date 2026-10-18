"""Public monthly fallback uses two actual PDFs and the actual official CSV."""
from pathlib import Path
from hashlib import sha256
from datetime import date
from copy import deepcopy
import base64,gzip,time
import pandas as pd
import pytest
from data_fetch.types import FetchRequest
from data_fetch.taiwan_providers import MonthlyRevenueProvider
F=Path(__file__).parent/'fixtures/source_acquisition';NEW=F/'twse_monthly_history_20261013'
CSV='https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv'
PDF='https://www.twse.com.tw/pdf/ch/2466_ch.pdf'
EXPECTED=['2026年4月: NT$0.71億','2026年5月: NT$0.46億','2026年6月: NT$1.19億','2026年7月: NT$1.94億','2026年8月: NT$2.25億','2026年9月: NT$1.16億']
@pytest.fixture
def original_http(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from official_response_evidence import archive_response
    from data_fetch.market_sources.official_company_legal_name import parse_roster
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    cache_store.set_cache_backend(InMemoryCache())
    raw=gzip.decompress((F/'nanya2408_complete_roster_20261011.json.gz').read_bytes());value=parse_roster(raw,'.TW');assert value['entries']['2466']['legal_name']=='冠西電子企業股份有限公司'
    now=time.time();archive_response(raw,source_url='https://openapi.twse.com.tw/v1/opendata/t187ap03_L',retrieved_at=now,http_status=200)
    key='shared_provider:v1:'+sha256(b'official-company-roster:v2:.TW').hexdigest();cache_store.set_cache_json(key,{'value':value,'fetched_at_epoch':now,'fresh_until_epoch':now+86400},86400)
    bodies={CSV:gzip.decompress((NEW/'listed.csv.gz').read_bytes()),PDF:gzip.decompress((NEW/'2466.pdf.gz').read_bytes())};calls=[]
    def download(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
        raw=bodies[url];return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    class EmptyLoader:
        def taiwan_stock_month_revenue(self,**kwargs):return pd.DataFrame()
    monkeypatch.setattr(IssuerNewsHttp,'_download',download)
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader',EmptyLoader)
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue._today',lambda:date(2026,10,13))
    monkeypatch.setenv('PROVIDER_RETRY_BACKOFF_SECONDS','0');monkeypatch.setenv('PROVIDER_RETRY_JITTER_SECONDS','0')
    yield calls,bodies,key
    cache_store.reset_cache_store_for_tests()
def test_public_failed_primary_recovers_six_contiguous_months_from_actual_official_history(original_http):
    calls,_,_=original_http;result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED
    assert result.audit['window_complete']is True and result.audit['covered_months']==[f'2026-{m:02d}'for m in range(4,10)]
    assert calls==[CSV,PDF] and result.audit['currency']=='NTD'
    assert result.audit['filed_amounts_NTD']==['70822000','45982000','119211000','194036000','224958000','116057000']
    assert result.audit['historical_point_in_time_verified']is False
    assert result.audit['related_entries'][0]['provider']=='FinMind TaiwanStockMonthRevenue'and result.audit['related_entries'][0]['status']=='unavailable'
def test_warm_history_does_not_renew_original_epoch_or_count_as_new_acquisition(original_http):
    from provider_acquisition import observation_kind
    calls,_,_=original_http;first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'));second=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert first.value==second.value==EXPECTED and calls==[CSV,PDF]
    assert second.status=='skipped_fresh_cache'and second.audit['cache_hit']is True and second.audit['http_request_sent']is False
    assert second.audit['fetched_at_epoch']==first.audit['fetched_at_epoch']
    assert observation_kind({**second.audit,'details':second.audit})=='fresh_cache_count'
def test_core_merge_uses_original_history_epoch_and_cache_flag(original_http):
    import asyncio
    from data_fetch.workflow import _run_missing_core_provider_plan
    from data_fetch.provider_registry import ProviderRegistry
    calls,_,_=original_http;first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'));data={'ticker':'2466.TW','recent_monthly_revenue':[],'source_audit':[]}
    result=asyncio.run(_run_missing_core_provider_plan(FetchRequest.from_ticker('2466.TW'),ProviderRegistry([MonthlyRevenueProvider()]),data))
    assert result['recent_monthly_revenue']==EXPECTED
    assert result['source_freshness']['monthly_revenue']['fetched_at_epoch']==first.audit['fetched_at_epoch']and result['source_freshness']['monthly_revenue']['cache_hit']is True
    assert calls==[CSV,PDF]
def test_successful_primary_keeps_original_route_without_new_pdf_request(original_http,monkeypatch):
    calls,_,_=original_http
    class Good:
        def taiwan_stock_month_revenue(self,**kwargs):return pd.DataFrame([{'revenue_year':2026,'revenue_month':9,'revenue':116057000}])
    monkeypatch.setattr('data_fetch.market_sources.taiwan.DataLoader',Good)
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'));assert result.provider=='FinMind TaiwanStockMonthRevenue'and not calls
def test_conflicting_fund_context_stops_all_requests(original_http):
    calls,_,_=original_http;data={'ticker':'2466.TW','quote_type':'ETF'};old=deepcopy(data);result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'),{'data':data})
    assert result.status=='not_applicable'and not calls and data==old

def test_cross_issuer_complete_pdf_cannot_replace_the_short_snapshot(original_http):
    calls,bodies,_=original_http;bodies[PDF]=gzip.decompress((NEW/'1301.pdf.gz').read_bytes())
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED[-2:]and result.audit['window_complete']is False
    assert calls==[CSV,PDF]
    failure=result.audit['related_entries'][-1]
    assert failure['status']=='error'and failure['record_count']==0 and failure['http_request_count']==1
    assert failure['error_kind']=='history_issuer_unverified'

def test_pdf_amount_must_match_exact_csv_amount_beyond_display_rounding(original_http):
    calls,bodies,_=original_http
    text=bodies[CSV].decode('utf-8-sig')
    import csv,io
    reader=csv.DictReader(io.StringIO(text,newline=''));fields=reader.fieldnames;rows=list(reader)
    row=next(r for r in rows if r['公司代號']=='2466');row['營業收入-當月營收']='116058'
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows);bodies[CSV]=stream.getvalue().encode()
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED[-2:]and result.audit['window_complete']is False
    assert result.audit['related_entries'][-1]['error_kind']=='history_snapshot_amount_or_unit_conflict'
    assert calls==[CSV,PDF]

@pytest.mark.parametrize('case,reason',[('missing','history_six_month_window_incomplete'),
                                     ('duplicate','history_monthly_period_duplicate'),
                                     ('future','history_production_date_future_or_expired'),
                                     ('partial','history_native_text_incomplete')])
def test_unqualified_native_pdf_result_keeps_old_partial_coverage(original_http,monkeypatch,case,reason):
    from data_fetch.market_sources import twse_monthly_history as history
    extract=history.extract_pdf_pages
    def corrupted(raw,**kwargs):
        pages=extract(raw,**kwargs)
        if case=='missing':pages['pages'][3]['text']=pages['pages'][3]['text'].replace('116,057,0002026/09','-2026/09')
        elif case=='duplicate':pages['pages'][3]['text']+='116,057,0002026/09\n'
        elif case=='future':pages['pages'][0]['text']=pages['pages'][0]['text'].replace('2026/10/13','2026/10/14')
        else:pages.update(coverage_status='partial',garbled_pages=[4])
        return pages
    monkeypatch.setattr(history,'extract_pdf_pages',corrupted)
    calls,_,_=original_http;result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED[-2:]and result.audit['window_complete']is False
    assert result.audit['related_entries'][-1]['error_kind']==reason and calls==[CSV,PDF]

def test_expired_issuer_original_does_not_enable_a_new_pdf_request(original_http):
    import cache_store
    calls,_,key=original_http;row=cache_store.get_cache_json(key);row['fetched_at_epoch']=time.time()-86401;row['fresh_until_epoch']=time.time()+30;cache_store.set_cache_json(key,row,30)
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED[-2:]and result.audit['window_complete']is False and calls==[CSV]

def test_same_fetch_primary_failure_is_preserved_once_when_history_recovers(original_http):
    from provider_correlation import correlation_scope
    from source_audit import audited_fetch
    calls,_,_=original_http
    with correlation_scope(replace=True,fetch_id='current',ticker='2466.TW'):
        first=audited_fetch('monthly_revenue',MonthlyRevenueProvider.name,lambda:[],default=[])
        data={'ticker':'2466.TW','source_audit':[first['audit']]};saved=deepcopy(data)
        result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'),{'data':data})
    assert result.value==EXPECTED and calls==[CSV,PDF]and data==saved
    assert result.audit['primary_failure_operation_id']==first['audit']['operation_id']
    assert all(x['provider']!='FinMind TaiwanStockMonthRevenue'for x in result.audit['related_entries'])

def test_csv_and_pdf_share_the_existing_eight_second_fallback_budget(original_http,monkeypatch):
    from data_fetch.market_sources import official_monthly_revenue as snapshot
    fetch=snapshot.fetch_official_monthly_revenue;monotonic=time.monotonic;now=[monotonic()]
    monkeypatch.setattr(time,'monotonic',lambda:now[0])
    def consume(ticker):
        value=fetch(ticker);now[0]+=8;return value
    monkeypatch.setattr(snapshot,'fetch_official_monthly_revenue',consume)
    calls,_,_=original_http;result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED[-2:]and result.audit['window_complete']is False and calls==[CSV]

def test_error_cache_blocks_native_reentry_without_recounting_a_new_failure(original_http):
    from provider_acquisition import observation_kind
    calls,bodies,_=original_http;bodies[PDF]=gzip.decompress((NEW/'1301.pdf.gz').read_bytes())
    first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'));old=deepcopy(first.audit['related_entries'][-1])
    second=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'));blocked=second.audit['related_entries'][-1]
    assert calls==[CSV,PDF]and first.value==second.value==EXPECTED[-2:]
    assert blocked['status']=='error'and blocked['record_count']==0 and blocked['http_request_count']==0
    assert blocked['http_request_sent']is False
    assert observation_kind({**blocked,'details':blocked})=='local_block_count'
    assert observation_kind({**old,'details':old})=='failed_count'
    assert first.audit['related_entries'][-1]==old

def test_conflicting_csv_name_cannot_promote_another_issuers_six_months(original_http):
    import csv,io
    calls,bodies,_=original_http
    reader=csv.DictReader(io.StringIO(bodies[CSV].decode('utf-8-sig'),newline=''))
    fields=reader.fieldnames;rows=list(reader)
    next(r for r in rows if r['公司代號']=='2466')['公司名稱']='台塑'
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fields)
    writer.writeheader();writer.writerows(rows);bodies[CSV]=stream.getvalue().encode()
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert result.value==EXPECTED[-2:] and result.audit['window_complete'] is False
    assert calls==[CSV]
    assert result.audit['related_entries'][-1]['error_kind']=='history_snapshot_issuer_or_amount_unverified'

def test_expiry_during_last_original_read_keeps_partial_instead_of_warm_success(original_http,monkeypatch):
    from data_fetch.market_sources import twse_monthly_history as history
    calls,_,_=original_http
    first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert first.value==EXPECTED
    receipt=first.audit['original_receipt'];clock=[first.audit['fetched_at_epoch']+1798.0]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    read=history.read_response;pdf_reads=[]
    def slow_read(arg):
        raw=read(arg)
        if arg['source_url']==PDF:
            pdf_reads.append(1)
            if len(pdf_reads)==2:clock[0]=receipt['retrieved_at']+1800.01
        return raw
    monkeypatch.setattr(history,'read_response',slow_read)
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert len(pdf_reads)==2 and calls==[CSV,PDF]
    assert result.value==EXPECTED[-2:] and result.audit['window_complete'] is False
    failure=result.audit['related_entries'][-1]
    assert failure['status']=='error' and failure['record_count']==0 and failure['http_request_sent'] is False
    assert failure['error_kind']=='history_original_receipt_unverified'

@pytest.mark.parametrize('constituent',['csv','master'])
def test_other_original_expiry_at_final_pdf_read_does_not_promote_six_months(original_http,monkeypatch,constituent):
    import cache_store
    from data_fetch.market_sources import twse_monthly_history as history
    from data_fetch.market_sources.official_monthly_revenue import PROVIDER
    calls,_,key=original_http
    master_epoch=cache_store.get_cache_json(key)['fetched_at_epoch']
    if constituent=='master':
        clock=[master_epoch+86398.0]
        monkeypatch.setattr(time,'time',lambda:clock[0])
    first=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert first.value==EXPECTED
    csv_epoch=next(a for a in first.audit['related_entries'] if a['provider']==PROVIDER)['original_receipt']['retrieved_at']
    pdf_epoch=first.audit['original_receipt']['retrieved_at']
    if constituent=='csv':
        assert pdf_epoch>csv_epoch
        clock=[csv_epoch+1798.0]
        expire_at=(csv_epoch+pdf_epoch)/2+1800
        monkeypatch.setattr(time,'time',lambda:clock[0])
    else:
        expire_at=master_epoch+86400.01
    read=history.read_response;pdf_reads=[]
    def slow_read(arg):
        raw=read(arg)
        if arg['source_url']==PDF:
            pdf_reads.append(1)
            if len(pdf_reads)==2:clock[0]=expire_at
        return raw
    monkeypatch.setattr(history,'read_response',slow_read)
    result=MonthlyRevenueProvider().fetch(FetchRequest.from_ticker('2466.TW'))
    assert len(pdf_reads)==2 and calls==[CSV,PDF]
    assert 0<=clock[0]-pdf_epoch<1800
    assert result.value==EXPECTED[-2:] and result.audit['window_complete'] is False
    failure=result.audit['related_entries'][-1]
    assert failure['error_kind']=='history_constituent_original_expired'
    assert failure['status']=='error' and failure['record_count']==0 and failure['http_request_sent'] is False
