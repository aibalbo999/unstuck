"""Official complete holding books repair actual 5880 gaps without relabeling facts."""
from copy import deepcopy
import pytest

DATA={'ticker':'5880.TW','company_name':'合庫金','instrument_type':'EQUITY','currency':'TWD','financial_currency':'TWD','sector':'Financial Services','industry':'Banks - Regional',
      'company_identity':{'ticker':'5880.TW','stock_id':'5880','official_name':'合庫金','legal_name':'合作金庫金融控股股份有限公司','official_ubn':'53021433','instrument_type':'EQUITY'}}

@pytest.mark.parametrize('identity',[
    {'ticker':'2886.TW'}, {'legal_name':'合作金庫商業銀行股份有限公司'},
    {'official_ubn':'70796754'}, {'stock_id':'2886'}, {'official_name':'兆豐金'},
    {'forbidden_aliases':['合庫金']},
])
def test_public_annual_refresh_rejects_tcfhc_identity_conflict_before_provider(identity):
    from data_fetch.annual_financial_source_provider import validate_context
    data=deepcopy(DATA);data['company_identity'].update(identity)
    with pytest.raises(ValueError):validate_context(data,'5880.TW')

def test_public_source_refresh_routes_the_failed_5880_issuer_to_published_books(monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.market_sources import tcfhc_annual_financial as books, financial_institution_xbrl as old
    from data_fetch.types import FetchRequest
    calls=[]
    def unavailable(*args,**kwargs):
        calls.append(kwargs)
        return {'value':None,'audit':{'source':'financial_statements','provider':books.PROVIDER,'status':'unavailable','record_count':0,'message':'isolated route boundary','cache_hit':False,'stale':False}}
    monkeypatch.setattr(books,'fetch_annual_result',unavailable)
    monkeypatch.setattr(old,'fetch_financial_institution_histories',lambda *a,**k: None)
    result=AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('5880.TW'),{'data':deepcopy(DATA)})
    assert len(calls)==1 and calls[0].get('force_refresh') is False
    assert result.audit['provider']==books.PROVIDER

from contextlib import nullcontext
from hashlib import sha256
from pathlib import Path
import gzip,json,time

E=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261014/remaining-four-next'
MASTER=Path(__file__).parent/'fixtures/source_acquisition/tcfhc5880_master_20261013.gz'

class Http:
    def __init__(self,*,cached=False,**kwargs):
        self.deadline=time.monotonic()+45;self.components=[];self.calls=[];self.cached=cached
    def batch(self):return nullcontext(self)
    def request(self,url):
        from data_fetch.market_sources.tcfhc_annual_transport import MASTER_URL,IR_URL
        from official_response_evidence import archive_response
        if url==MASTER_URL:raw=gzip.open(MASTER,'rb').read()
        elif url==IR_URL:raw=(E/'tcfhc-audited-financial-english-index.body').read_bytes()
        else:
            found=[]
            for year in range(2021,2026):
                r=json.loads((E/f'tcfhc-audited-{year}-english-pdf.receipt.json').read_text())
                if r['url']==url:found.append(year)
            assert len(found)==1
            raw=(E/f'tcfhc-audited-{found[0]}-english-pdf.body').read_bytes()
        self.calls.append(url)
        receipt=archive_response(raw,source_url=url,retrieved_at=time.time()-100 if self.cached else time.time(),http_status=200)
        receipt.update(http_status_observed=True,request_method='GET',response_complete=True,cache_hit=self.cached)
        self.components.append({'url':url,'http_request_sent':not self.cached,'http_status':200,'cache_hit':self.cached,'status':'complete','response_bytes':len(raw),'response_sha256':sha256(raw).hexdigest()})
        return raw,receipt

@pytest.fixture(scope='module')
def packet():
    from data_fetch.market_sources.tcfhc_annual_financial import fetch_annual_histories
    return fetch_annual_histories('5880.TW',transport=Http())

def wire(monkeypatch,**kw):
    from data_fetch.market_sources import tcfhc_annual_financial as books
    http=Http(**kw);monkeypatch.setattr(__import__('data_fetch.market_sources.tcfhc_annual_transport',fromlist=['AnnualHttp']),'AnnualHttp',lambda **kwargs:http)
    return http

def test_five_native_books_reconcile_restatement_and_missing_fcf(packet):
    from data_fetch.market_sources.tcfhc_annual_financial import project_annual_statement
    assert packet['years']==['2021','2022','2023','2024','2025']
    assert packet['raw_twd_by_year']['2021']['free_cash_flow']==57_997_511_000
    assert packet['raw_twd_by_year']['2023']['assets']==4_797_206_197_000
    assert packet['raw_twd_by_year']['2025']['net_income_attributable']==21_294_771_000
    assert any(r['year']==2023 and r['fact']=='ifrs-full:Assets' and r['kind']=='restatement' and r['original_twd']==4_803_702_956_000 for r in packet['comparative_revisions'])
    assert project_annual_statement(packet,'5880.TW')==packet

def test_typed_holding_projection_never_fills_general_industry_values(packet):
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder_helpers import _prompt_financial_institution_history
    p=project_source_value(packet,'5880.TW');assert p is not None
    for key in ('revenue_history','gross_profit_history','operating_income_history'):assert p[key]==[None]*5
    assert len(p['net_revenue_history'])==5 and p['fcf_history'][0]==57.997511
    data={**DATA,**p};prompt=_prompt_financial_institution_history(data)
    assert 'Chinese_original_prevails' in prompt['basis_note']
    assert all('raw_response_path' not in str(r) for r in prompt['rows'])

@pytest.mark.parametrize('change',[
    lambda v:v.update(ticker='2886.TW'),lambda v:v.update(currency='USD'),lambda v:v.update(schema='financial_holding_public_annual.v1'),
    lambda v:v['raw_twd_by_year']['2021'].update(free_cash_flow=0),lambda v:v['raw_twd_by_year']['2021'].update(assets=True),
    lambda v:v['documents'][0].update(year=True),lambda v:v['documents'][0].update(url=v['documents'][1]['url']),
    lambda v:v['documents'][0]['raw_receipt'].update(http_status=403),
    lambda v:v['documents'][0]['raw_receipt'].update(raw_response_sha256='0'*64),
    lambda v:v.update(comparative_revisions=[]),lambda v:v['documents'][0]['parsed_book_basis']['facts']['2021'].update({'ifrs-full:Assets':0}),
    lambda v:v.update(report_scope='standalone'),lambda v:v.update(source_basis='unverified'),
])
def test_saved_statement_cannot_substitute_facts_or_receipts(packet,change):
    from data_fetch.market_sources.tcfhc_annual_financial import project_annual_statement
    v=deepcopy(packet);change(v);assert project_annual_statement(v,'5880.TW') is None

def test_actual_source_provider_returns_seven_distinct_requests_and_complete_years(monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope
    h=wire(monkeypatch)
    with correlation_scope(replace=True,ticker='5880.TW',fetch_id='isolated-source-only-tcfhc'):
        result=AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('5880.TW'),{'data':deepcopy(DATA)})
    assert result.audit['status']=='success' and result.audit['record_count']==5, result.audit
    assert result.audit['cache_hit'] is False and result.audit['http_request_count']==7
    assert len(h.calls)==len(set(h.calls))==7
    assert result.value['raw_twd_by_year']['2021']['free_cash_flow']==57_997_511_000

def test_warm_originals_preserve_epochs_and_do_not_count_as_new_acquisition(monkeypatch):
    from data_fetch.market_sources.tcfhc_annual_financial import fetch_annual_result
    from provider_acquisition import project_acquisition_events
    h=wire(monkeypatch,cached=True);r=fetch_annual_result('5880.TW');a=r['audit']
    assert r['value'] is not None and a['status']=='success' and a['cache_hit'] is True
    assert a['http_request_sent'] is False and a['http_request_count']==0
    assert 99<=time.time()-a['fetched_at_epoch']<1800
    event={**a,'created_at':time.time(),'details_json':json.dumps(a)}
    sources=project_acquisition_events([event],window='last_24h',now=time.time())['sources']
    assert sources[0]['fetched_count']==0 and sources[0]['fetch_attempts']==0

def test_normal_financial_path_uses_published_books_without_sdk_or_finmind(monkeypatch):
    from data_fetch.yfinance_extractors import extract_financial_histories
    from provider_correlation import correlation_scope
    h=wire(monkeypatch);monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK');notes=[]
    class NoSDK:
        def __getattr__(self,name):raise AssertionError('unnecessary annual SDK '+name)
    with correlation_scope(replace=True,ticker='5880.TW',fetch_id='isolated-tcfhc-annual'):
        result=extract_financial_histories(NoSDK(),'5880.TW',notes,quote_type='EQUITY',industry_context='Financial Services Banks - Regional')
    audit=result['sector_specific_financial_audit']
    assert result['years']==['2021','2022','2023','2024','2025'] and result['revenue_history']==[None]*5
    assert result['fcf_history'][0]==57.997511 and audit['http_request_count']==7
    assert len(h.calls)==7 and any('英文' in n and '中文' in n for n in notes)
    assert result['primary_financial_audit'] is None and result['finmind_financial_fallback_audit'] is None

def test_source_only_refresh_preserves_prior_report_and_quality_gates(monkeypatch,tmp_path):
    import asyncio
    from test_report_annual_financial_source_refresh import report
    from test_report_refresh_acquisition_audit import init_db
    from report_refresh_service import refresh_report_data_snapshot
    from data_fetch.service import StockDataService
    init_db();wire(monkeypatch);storage,name,keys,old=report('5880.TW');old['data'].update(deepcopy(DATA))
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='financial_statements'))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert saved['data']['fcf_history'][0]==57.997511 and saved['data']['revenue_history']==[None]*5
    assert saved['analysis_evidence']==old['analysis_evidence'] and storage.get_report(keys.html_key).content==b'original conclusions'
    assert saved['data']['current_price']==old['data']['current_price']
    assert any('英文' in n and '重編' in n for n in saved['data']['data_source_notes'])

def test_all_seven_originals_must_still_be_fresh_at_completion(monkeypatch,packet):
    from data_fetch.market_sources import tcfhc_annual_financial as books
    from data_fetch.market_sources.tcfhc_annual_transport import MASTER_URL
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    from official_response_evidence import archive_response
    real_time=time.time;clock=[real_time()];parse=books._book
    class NearlyExpired(Http):
        def request(self,url):
            raw,receipt=super().request(url)
            if url==MASTER_URL:
                receipt=archive_response(raw,source_url=url,retrieved_at=clock[0]-1799,http_status=200)
                receipt.update(http_status_observed=True,request_method='GET',response_complete=True,cache_hit=True)
            return raw,receipt
    def complete_last(raw,year,deadline=None):
        parsed=parse(raw,year,deadline)
        if year==2025:clock[0]+=2
        return parsed
    monkeypatch.setattr(time,'time',lambda:clock[0]);monkeypatch.setattr(books,'_book',complete_last)
    with pytest.raises(FilingError,match='TTL expired'):
        books.fetch_annual_histories('5880.TW',transport=NearlyExpired())

def test_parse_cache_never_hides_corrupted_original_archive(packet):
    from data_fetch.market_sources import tcfhc_annual_financial as books
    assert books.project_annual_statement(packet,'5880.TW')==packet
    path=Path(packet['documents'][0]['raw_receipt']['raw_response_path']);original=path.read_bytes()
    try:
        path.write_bytes(b'corrupt gzip after successful parse')
        assert books.project_annual_statement(packet,'5880.TW') is None
    finally:
        path.write_bytes(original)

def test_unexpected_local_failure_does_not_redownload_whole_batch():
    from data_fetch.market_sources.tcfhc_annual_financial import fetch_annual_result
    class FailedLocal(Http):
        def request(self,url):
            self.calls.append(url)
            raise OSError('isolated archive write failure')
    h=FailedLocal();r=fetch_annual_result('5880.TW',transport=h)
    assert r['value'] is None and r['audit']['record_count']==0
    assert len(h.calls)==1 and r['audit']['http_request_count']==0
