from pathlib import Path
from datetime import datetime,date
from copy import deepcopy
import base64,json,time
import pandas as pd
import pytest
from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
from data_fetch.types import FetchRequest
from data_fetch.market_sources import peers
from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp,ROSTER_URL

F=json.loads((Path(__file__).parent/'fixtures/source_acquisition/medtecs_medical_cohort_20261010.json').read_text())
TODAY=date(2026,10,10)
DATA={'ticker':'9103.TW','company_name':'美德醫療-DR / Medtecs International Corporation Limited',
      'sector':'Healthcare','industry':'Medical Instruments & Supplies',
      'company_identity':{'ticker':'9103.TW','stock_id':'9103','instrument_type':'EQUITY','official_name':'美德醫療-DR','legal_name':None}}
MATCHED={'4107.TWO','4116.TWO','4126.TWO','4735.TWO','6730.TWO'}

def boundaries(monkeypatch,*,quotes=None,roster=None,html=None,master=None):
    # Replay the captured cohort and issuer roster on their declared date.
    from datetime import timezone
    from data_fetch.market_sources import moneydj_medical_peer_cohort as cohort
    monkeypatch.setattr(time, 'time', lambda: datetime(2026, 10, 10, 4, tzinfo=timezone.utc).timestamp())
    monkeypatch.setattr(cohort, '_today', lambda: TODAY)
    calls=[];infos={r['ticker']:r['sdk_fields'] for r in F['native_quote_research']}
    if quotes:infos.update(quotes)
    def get(http,url):
        calls.append(url);http.components.append({'url':url,'cache_hit':False,'http_request_sent':False,'fetched_at_epoch':time.time()})
        return json.dumps(F['selected_official_roster_rows'] if roster is None else roster,ensure_ascii=False).encode() if url==ROSTER_URL else (base64.b64decode(F['raw_html_base64']) if html is None else html)
    class Stock:
        def __init__(self,ticker):self.info=deepcopy(infos[ticker]);self.ticker=ticker
        # Synthetic same-period frames exercise acquisition behavior, not live financial values.
        @property
        def financials(self):return pd.DataFrame([[500]],index=['Total Revenue'],columns=pd.to_datetime(['2025-12-31']))
        @property
        def balance_sheet(self):return pd.DataFrame([[1000]],index=['Total Assets'],columns=pd.to_datetime(['2025-12-31']))
    monkeypatch.setattr(peers,'load_peer_stock_master',lambda:deepcopy(F['master_rows'] if master is None else master))
    monkeypatch.setattr(peers,'_today',lambda:TODAY)
    monkeypatch.setattr(peers.yf,'Ticker',Stock);monkeypatch.setattr(IssuerNewsHttp,'get',get)
    return calls

def test_public_peer_provider_recovers_numeric_rows_for_a_current_tdr_without_using_stale_master_identity(monkeypatch):
    boundaries(monkeypatch);before=deepcopy(DATA)
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':DATA})
    assert result.status=='success' and result.audit['record_count']==5
    assert {r['ticker'] for r in result.value}==MATCHED
    assert result.audit['candidate_attempt_count']<=10 and result.audit['business_industry_rejected_count']==5
    assert all(r['metrics_status']=='complete' and r['business_comparability_verified_current'] is False for r in result.value)
    assert DATA==before
    from prompt_builder import format_data_for_prompt
    payload=deepcopy(DATA);payload['dynamic_peer_metrics']=result.value;prompt=format_data_for_prompt(payload)
    structured,_=json.JSONDecoder().raw_decode(prompt[prompt.index('{'):]);assert structured['peer_context']['dynamic_peer_metrics']==[]

def test_formal_sync_assembly_preserves_typed_peer_partial_status_and_diagnostics(monkeypatch):
    from data_fetch import yfinance_sync_enrichment as sync
    from data_fetch.types import ProviderResult
    from data_fetch import institutional_provider
    import source_applicability
    monkeypatch.setattr(source_applicability,'source_is_applicable',lambda source,data:source!='institutional_trading')
    specs=[]
    monkeypatch.setattr(sync,'_run_named_fetches',lambda fetches,**kwargs:(specs.extend(fetches)or{'values':{},'audit':[]}))
    row={'ticker':'4107.TWO','metrics_status':'partial','business_comparability_verified_current':False}
    audit={'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','status':'degraded_enrichment','record_count':1,
           'coverage_status':'partial','quality_status':'partial_metrics','candidate_attempt_count':10}
    monkeypatch.setattr(DynamicPeerMetricsProvider,'fetch',lambda *a,**k:ProviderResult(source='dynamic_peer_metrics',provider='FinMind/yfinance',value=[row],status='degraded_enrichment',audit=audit))
    result=sync.fetch_sync_enrichment_bundle(ticker='9103.TW',stock=None,company_name=DATA['company_name'],sector=DATA['sector'],industry=DATA['industry'],company_identity=DATA['company_identity'],years=[],net_income_history=[],shares_outstanding=None,skip_optional_http=True)
    assert 'dynamic_peer_metrics' not in specs
    assert result['dynamic_peer_metrics']==[row]
    assert next(a for a in result['audit'] if a['source']=='dynamic_peer_metrics')==audit

@pytest.mark.parametrize('field,value',[('symbol',None),('symbol','2330.TW'),('quoteType',None),('quoteType','ETF'),('industry',None),('industry','Banks - Regional')])
def test_quote_identity_and_fine_industry_cannot_be_inferred_from_publisher_membership(monkeypatch,field,value):
    info=deepcopy(next(r['sdk_fields'] for r in F['native_quote_research'] if r['ticker']=='4107.TWO'));info[field]=value
    boundaries(monkeypatch,quotes={'4107.TWO':info})
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':DATA})
    assert '4107.TWO' not in {r['ticker']for r in result.value}
    assert result.audit['usable_count']==4

@pytest.mark.parametrize('change',['wrong_legal','wrong_short','stale','future','wrong_country','duplicate'])
def test_unverified_current_target_roster_cannot_use_stale_finmind_tdr_membership(monkeypatch,change):
    roster=deepcopy(F['selected_official_roster_rows'])
    if change=='wrong_legal':roster[0]['公司名稱']='其他公司股份有限公司'
    elif change=='wrong_short':roster[0]['公司簡稱']='其他公司'
    elif change=='stale':roster[0]['出表日期']='1150901'
    elif change=='future':roster[0]['出表日期']='1151011'
    elif change=='wrong_country':roster[0]['外國企業註冊地國']='US 美國'
    else:roster.append(deepcopy(roster[0]))
    calls=boundaries(monkeypatch,roster=roster)
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':DATA})
    assert result.value==[] and result.status!='success'
    assert calls==[ROSTER_URL]

@pytest.mark.parametrize('change',['missing_target','wrong_target','duplicate_target','missing_date','stale','future','wrong_title','wrong_peer_name'])
def test_ambiguous_or_unverified_publisher_cohort_is_not_a_numeric_data_source(monkeypatch,change):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(base64.b64decode(F['raw_html_base64']).decode('big5'),'html.parser')
    table=soup.find('table',id='oMainTable')
    link=next(a for a in table.find_all('a',href=True) if "AS9103" in a['href']);tr=link.find_parent('tr')
    if change=='missing_target':tr.decompose()
    elif change=='wrong_target':link.string='9103其他公司'
    elif change=='duplicate_target':tr.parent.append(deepcopy(tr))
    elif change=='wrong_title':soup.title.string='同業股價表現-其他產業'
    elif change=='wrong_peer_name':next(a for a in table.find_all('a',href=True) if 'AS4107' in a['href']).string='4107其他公司'
    else:
        text=next(t for t in tr.find_all(string=True) if '2026/10/08' in t)
        text.replace_with({'missing_date':'日期未知','stale':'2026/09/01','future':'2026/10/11'}[change])
    boundaries(monkeypatch,html=str(soup).encode('big5',errors='xmlcharrefreplace'))
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':DATA})
    assert result.value==[] and result.status!='success'

def test_peer_ttm_assets_cannot_skip_same_period_annual_asset_turnover(monkeypatch):
    info=deepcopy(next(r['sdk_fields'] for r in F['native_quote_research'] if r['ticker']=='4107.TWO'));info.update(totalRevenue=900,totalAssets=100)
    boundaries(monkeypatch,quotes={'4107.TWO':info})
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':DATA})
    peer=next(r for r in result.value if r['ticker']=='4107.TWO')
    assert peer['asset_turnover']==.5 and peer['metric_sources']['asset_turnover']['observed_at']=='2025-12-31'

@pytest.mark.parametrize('mode',['cold','warm','mixed','http_failure','local_block','invalid_cached_page'])
def test_public_audit_flatten_preserves_composite_source_transport_and_original_cache_receipts(monkeypatch,mode):
    from data_fetch.workflow import _audit_entries_from_provider_results
    from provider_observation_details import observation_details
    from search_provider_runtime import SourceResponseError
    boundaries(monkeypatch)
    original_epoch=time.time()-60
    def get(http,url):
        cached=mode in {'warm','invalid_cached_page'} or mode=='mixed' and url!=ROSTER_URL
        sent=not cached and mode!='local_block'
        component={'url':url,'cache_hit':cached,'http_request_sent':sent,'fetched_at_epoch':original_epoch}
        http.components.append(component);http.http_request_count+=int(sent)
        if mode in {'http_failure','local_block'} and url==ROSTER_URL:
            component['error_kind']='server_error' if sent else 'cooldown'
            raise SourceResponseError(component['error_kind'])
        raw=json.dumps(F['selected_official_roster_rows'],ensure_ascii=False).encode() if url==ROSTER_URL else base64.b64decode(F['raw_html_base64'])
        return raw.replace(b'oMainTable',b'invalidTable') if mode=='invalid_cached_page' and url!=ROSTER_URL else raw
    monkeypatch.setattr(IssuerNewsHttp,'get',get)
    result=DynamicPeerMetricsProvider().fetch(FetchRequest.from_ticker('9103.TW'),{'data':DATA})
    children=[a for a in _audit_entries_from_provider_results([result]) if a['source']=='peer_discovery']
    assert len(children)==1
    audit=children[0];detail=observation_details(audit)
    expected_kind='http_request' if mode in {'cold','mixed','http_failure'} else 'cache_hit' if mode in {'warm','invalid_cached_page'} else 'local_block'
    assert audit['event_kind']==expected_kind and detail['http_request_sent']==(expected_kind=='http_request')
    assert audit['status']==('skipped_fresh_cache' if mode=='warm' else 'success' if mode in {'cold','mixed'} else 'error')
    assert audit['record_count']==(10 if mode in {'cold','warm','mixed'} else 0)
    assert detail['usable_count']==audit['record_count']
    components=detail['component_statuses']
    assert components['official_issuer_identity']['fetched_at_epoch']==original_epoch
    if mode in {'cold','warm','mixed'}:
        assert components['medical_candidate_cohort']['fetched_at_epoch']==original_epoch
        assert components['medical_candidate_cohort']['observation_status']==('http_request' if mode=='cold' else 'cache_hit')
        assert len(components['medical_candidate_cohort']['response_sha256'])==64
    assert detail['quality_status']=='candidate_relationship_only'
