"""Exact official railway leads, not cross-currency valuation comparability."""
from pathlib import Path
from datetime import datetime,date,timezone
import importlib.util
import gzip,json,time

import pandas as pd
import pytest

FIXTURES=Path(__file__).parent/'fixtures/source_acquisition/rail_jpx_20261103'
TARGET='2633.TW'
SYMBOLS=['9020.T','9021.T','9022.T','9142.T']
TODAY=date(2026,11,3)


def body(name):return gzip.decompress((FIXTURES/(name+'.gz')).read_bytes())


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import peers
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time,'time',lambda:datetime(2026,11,3,8,tzinfo=timezone.utc).timestamp())
    monkeypatch.setattr(peers,'_today',lambda:TODAY)
    import thermal_peer_source_refresh
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return cls.fromtimestamp(time.time(),tz)
    monkeypatch.setattr(thermal_peer_source_refresh,'datetime',Clock)
    yield
    cache_store.reset_cache_store_for_tests()


class Stock:
    def __init__(self,symbol):self.symbol=symbol
    @property
    def info(self):
        return {'symbol':self.symbol,'quoteType':'EQUITY','currency':'JPY','financialCurrency':'JPY',
                'industry':'Railroads','grossMargins':.4,'operatingMargins':.2,'profitMargins':.1,
                'returnOnEquity':.09,'trailingPE':12.,'priceToBook':1.2,'priceToSalesTrailing12Months':2.,
                'totalRevenue':999,'totalAssets':1}
    @property
    def financials(self):return pd.DataFrame({pd.Timestamp('2026-03-31'):[40.]},index=['Total Revenue'])
    @property
    def balance_sheet(self):return pd.DataFrame({pd.Timestamp('2026-03-31'):[50.]},index=['Total Assets'])


def native_boundary(monkeypatch):
    """Mock only native process/HTTP and SDK boundaries; actual parsers replay bodies."""
    from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
    import base64
    native=[]
    urls={'https://openapi.twse.com.tw/v1/opendata/t187ap03_L':'listed.json',
          'https://www.thsrc.com.tw/corp/a021c60f-4a63-44df-8332-1f0920615c48':'issuer.html',
          'https://global.jr-central.co.jp/en/company/about/area.html':'central.html',
          'https://www.jrkyushu.co.jp/english/company.html':'kyushu-company.html',
          'https://www.jrkyushu.co.jp/english/train/index.html':'kyushu-trains.html',
          'https://www2.jpx.co.jp/disc/90200/140120260430514919.pdf':'annual9020.pdf',
          'https://www2.jpx.co.jp/disc/90210/140120260430515241.pdf':'annual9021.pdf'}
    def download(self,url,diagnostic):
        native.append(url);self.http_request_count+=1;diagnostic['http_request_sent']=True
        raw=body(urls[url])
        from hashlib import sha256
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest()}
    monkeypatch.setattr(IssuerNewsHttp,'_download',download)
    name='data_fetch.market_sources.jpx_company_transport'
    if importlib.util.find_spec(name) is not None:
        module=__import__(name,fromlist=['_run_curl'])
        def curl(argv,deadline,*,body_limit,headers):
            from urllib.parse import parse_qs
            url=argv[-1];raw=body('entry.html')
            if '--data-raw'in argv:
                fields=parse_qs(argv[argv.index('--data-raw')+1],keep_blank_values=True)
                code=(fields.get('eqMgrCd')or fields.get('mgrCd'))[0][:4]
                raw=body(('details'if 'JJK020030Action'in url else'search')+code+'.html')
            native.append(url)
            meta={'http_code':200,'url_effective':url,'num_redirects':0,'ssl_verify_result':0,'proxy_used':0,'size_download':len(raw)}
            return {'process_started':True,'body':raw,'headers':b'HTTP/2 200\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n','metadata':json.dumps(meta).encode()},0,None
        monkeypatch.setattr(module,'_run_curl',curl)
    return native


def test_normal_source_recovers_all_four_official_railway_leads(monkeypatch):
    from data_fetch.market_sources import peers
    from prompt_peer_projection import comparable_peer_rows
    from stock_snapshot.peers_valuation import _peer_comparison
    native_boundary(monkeypatch)
    monkeypatch.setattr(peers,'load_peer_stock_master',lambda:[])
    monkeypatch.setattr(peers.yf,'Ticker',Stock)
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET,'台灣高鐵','Industrials','Railroads',{})
    assert [r['ticker']for r in result['peers']]==SYMBOLS,{k:result['audit'].get(k)for k in ('official_rail_candidate_status','official_rail_candidate_details')}
    assert result['audit']['usable_count']==4
    assert result['audit']['coverage_status']=='success'
    assert all(r['business_comparability_verified_current']is False for r in result['peers'])
    assert comparable_peer_rows(result['peers'])==[]
    assert _peer_comparison({'ticker':TARGET,'dynamic_peer_metrics':result['peers']})['summary']['peer_count']==0
    for r in result['peers']:
        assert r['asset_turnover']==.8
        assert r['metric_sources']['asset_turnover']['observed_at']=='2026-03-31'
        assert r['metric_sources']['asset_turnover']['currency']=='JPY'


def test_source_only_accepts_exact_thsrc_equity_context():
    from peer_source_refresh import validate_peer_refresh_context
    data={'ticker':TARGET,'company_name':'台灣高鐵 / Taiwan High Speed Rail Corporation',
          'quote_type':'EQUITY','dynamic_peer_metrics':[]}
    assert validate_peer_refresh_context(data,TARGET)=='railway'


@pytest.mark.parametrize('change',['quote_currency','financial_currency','missing_currency','wrong_symbol','not_equity'])
def test_unverified_quote_currency_or_identity_cannot_supply_railway_metrics(monkeypatch,change):
    from data_fetch.market_sources import peers
    native_boundary(monkeypatch)
    class InvalidStock(Stock):
        @property
        def info(self):
            data=super().info
            if change=='quote_currency':data['currency']='USD'
            elif change=='financial_currency':data['financialCurrency']='USD'
            elif change=='missing_currency':data.pop('financialCurrency')
            elif change=='wrong_symbol':data['symbol']='9999.T'
            elif change=='not_equity':data['quoteType']='ETF'
            return data
    monkeypatch.setattr(peers.yf,'Ticker',InvalidStock)
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET,'台灣高鐵','Industrials','Railroads',{})
    assert result['peers']==[]and result['audit']['usable_count']==0
    assert result['audit']['coverage_status']=='unavailable'


@pytest.mark.parametrize('change',['different_dates','wrong_fiscal_month','old_period'])
def test_missing_common_annual_period_keeps_ratio_unknown(monkeypatch,change):
    from data_fetch.market_sources import peers
    native_boundary(monkeypatch)
    class InvalidPeriodStock(Stock):
        @property
        def financials(self):
            period='2025-12-31'if change=='wrong_fiscal_month'else'2024-03-31'if change=='old_period'else'2026-03-31'
            return pd.DataFrame({pd.Timestamp(period):[40.]},index=['Total Revenue'])
        @property
        def balance_sheet(self):
            period='2025-12-31'if change=='wrong_fiscal_month'else'2024-03-31'if change=='old_period'else'2025-03-31'
            return pd.DataFrame({pd.Timestamp(period):[50.]},index=['Total Assets'])
    monkeypatch.setattr(peers.yf,'Ticker',InvalidPeriodStock)
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET,'台灣高鐵','Industrials','Railroads',{})
    assert len(result['peers'])==4
    assert all(r['asset_turnover']is None for r in result['peers'])
    assert all('asset_turnover'in r['missing_metrics']for r in result['peers'])
    assert result['audit']['coverage_status']=='partial'


def test_one_unavailable_member_keeps_three_good_references_but_not_full_success(monkeypatch):
    from data_fetch.market_sources import peers,jpx_company_transport as transport
    from search_provider_runtime import SourceResponseError
    native_boundary(monkeypatch);get=transport.JpxCompanyGateway.get
    def unavailable(self,code,**kw):
        if code=='90210':raise SourceResponseError('access_denied')
        return get(self,code,**kw)
    monkeypatch.setattr(transport.JpxCompanyGateway,'get',unavailable)
    monkeypatch.setattr(peers.yf,'Ticker',Stock)
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET,'台灣高鐵','Industrials','Railroads',{})
    assert [r['ticker']for r in result['peers']]==['9020.T','9022.T','9142.T']
    assert result['audit']['coverage_status']=='partial'and result['audit']['expected_candidate_count']==4
    assert result['audit']['official_rail_candidate_details']['unqualified_members']['9021.T']=='access_denied'


def test_unavailable_gateway_does_not_download_unrelated_legacy_neighbors(monkeypatch):
    from data_fetch.market_sources import peers,jpx_company_transport as transport
    from search_provider_runtime import SourceResponseError
    native_boundary(monkeypatch)
    def unavailable(*a,**kw):raise SourceResponseError('cooldown')
    def forbidden(*a,**kw):pytest.fail('No unrelated issuer or quote may be downloaded')
    monkeypatch.setattr(transport.JpxCompanyGateway,'get',unavailable)
    monkeypatch.setattr(peers,'load_peer_stock_master',forbidden)
    monkeypatch.setattr(peers.yf,'Ticker',forbidden)
    result=peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET,'台灣高鐵','Industrials','Railroads',{})
    assert result['peers']==[]and result['audit']['candidate_attempt_count']==0


def test_expired_member_original_cannot_validate_post_acquisition_rows(monkeypatch):
    from copy import deepcopy
    from data_fetch.market_sources import peers,official_railway_peer_cohort as source
    native_boundary(monkeypatch);monkeypatch.setattr(peers.yf,'Ticker',Stock)
    rows=peers.fetch_dynamic_peer_metrics_with_diagnostics(TARGET,'台灣高鐵','Industrials','Railroads',{})['peers']
    assert source.verified_candidates(rows,TARGET,today=TODAY)
    for change in ('expired','duplicate','upgrade','wrong_target'):
        bad=deepcopy(rows)
        if change=='expired':bad[0][source.RECEIPT_KEY]['jpx']['originals'][1]['retrieved_at']=time.time()-1801
        elif change=='duplicate':bad[1]=deepcopy(bad[0])
        elif change=='upgrade':bad[0]['numeric_comparability_verified']=True
        elif change=='wrong_target':bad[0]['issuer_master_anchor']['ticker']='2634.TW'
        assert not source.verified_candidates(bad,TARGET,today=TODAY)


def test_public_source_refresh_preserves_original_prices_claims_gates_and_analysis(monkeypatch,tmp_path):
    import asyncio
    from data_fetch.market_sources import peers
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_analysis_evidence import capture_analysis_evidence
    from report_persistence import report_bundle_keys_for_filename
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_thermal_peer_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db,events
    init_db();native_boundary(monkeypatch);monkeypatch.setattr(peers.yf,'Ticker',Stock)
    storage=InMemoryStorage();_,old_keys,old=saved_report(storage)
    old['ticker']=old['data']['ticker']=TARGET
    old['company_name']=old['data']['company_name']='台灣高鐵 / Taiwan High Speed Rail Corporation'
    old['data'].update(sector='Industrials',industry='Railroads')
    old['analysis_evidence']=capture_analysis_evidence({'data':old['data']},generated_at=old['generated_at'])
    filename='2633_TW_v1_report_20261103_080000.html';keys=report_bundle_keys_for_filename(filename)
    for new,original in [(keys.html_key,old_keys.html_key),(keys.md_key,old_keys.md_key)]:storage.save_report(new,storage.get_report(original).content,content_type='text/plain')
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    flags=[]
    class ObservedProvider(DynamicPeerMetricsProvider):
        def fetch(self,request,context=None):
            flags.append(request.options.force_refresh);return super().fetch(request,context)
    def forbidden(*a,**kw):pytest.fail('Source-only must not fetch core data or models')
    service=StockDataService(registry=ProviderRegistry([ObservedProvider(),CallableProvider('market_data','forbidden',forbidden)]))
    response=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,refresh_service=service,source='dynamic_peer_metrics',return_refreshed_data=True))
    updated=json.loads(storage.get_report(keys.data_key).content)
    assert [r['ticker']for r in updated['data']['dynamic_peer_metrics']]==SYMBOLS
    for key in ('current_price','revenue_history','years','peer_discovery_results'):assert updated['data'][key]==old['data'][key]
    assert updated['analysis_evidence']==old['analysis_evidence']
    for gate in ('report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert updated[gate]==old[gate]
    assert next(a for a in updated['source_audit']if a['source']=='market_data')==old['source_audit'][0]
    assert storage.get_report(keys.html_key).content==b'<html>unchanged conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'unchanged conclusions'
    assert response['analysis_text_stale']is True and flags==[False]
    recorded=events();assert recorded and all(e['source']=='dynamic_peer_metrics'for e in recorded)
    native=[json.loads(e['details_json'])for e in recorded if json.loads(e['details_json']).get('event_kind')=='http_transport_receipt']
    assert native and all(d.get('original_http_receipts')for d in native)
    assert all('jsessionid='not in json.dumps(d)for d in native)


def test_forced_source_only_refresh_rejected_before_provider(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    import data_fetch.service as module
    async def forbidden(*a,**kw):pytest.fail('No provider may be called')
    monkeypatch.setattr(module,'fetch_correlated_provider',forbidden)
    with pytest.raises(HTTPException)as e:
        asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker(TARGET,force_refresh=True),'dynamic_peer_metrics',context={'data':{'ticker':TARGET,'company_name':'台灣高鐵','instrument_type':'EQUITY','dynamic_peer_metrics':[]}}))
    assert e.value.status_code==400
