"""Normal audited proof and cold master gates for the exact foreign issuer."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from test_peer_reference_evidence import evidence_environment,DAY
from test_consolidated_peer_evidence import normal_frame
from test_gourmet_parent_income import body,TICKER
from test_peer_reference_income import reference_body,index_body
from test_peer_reference_transport import parts

@pytest.fixture
def gourmet_environment(evidence_environment,monkeypatch):
    from data_fetch.market_sources import peer_reference_evidence as e,peer_reference_transport as t
    store,calls,meta=evidence_environment;raw,_=e.read_cached_listed_roster_bytes();rows=json.loads(raw)
    rows[-1].update({'公司代號':'2723','公司名稱':'開曼美食達人股份有限公司','公司簡稱':'美食-KY','營利事業統一編號':'39682101','產業別':'16','已發行普通股數或TDR原股發行股數':'180000000','外國企業註冊地國':'KY 開曼群島    '})
    def master():
        raw=json.dumps(rows,ensure_ascii=False).encode();meta.update(source_payload_sha256=sha256(raw).hexdigest(),source_payload_bytes=len(raw));return raw,deepcopy(meta)
    monkeypatch.setattr(e,'read_cached_listed_roster_bytes',master);old=t.PeerIncomeHttp._download
    def download(self,request,diagnostic):
        kind,p=request['kind'],request['params']
        if kind in ['home','methodology']:return old(self,request,diagnostic)
        calls.append(deepcopy(request))
        if kind=='reference':
            v=json.loads(reference_body());v['data'][-1][:2]=['2723','美食-KY'];raw=json.dumps(v,ensure_ascii=False).encode()
        elif kind=='index':raw=index_body(p['year'],[2]if p['year']==2026 else[2,4]).decode('big5').replace('6230','2723').replace('尼得科超眾','美食-KY').encode('big5')
        else:
            parent,nci,eps={(2026,2):(574918,9727,'3.19'),(2025,2):(329000,7993,'1.83'),(2025,4):(-443839,9859,'-2.47')}[(p['year'],p['quarter'])]
            raw=body(p['year'],p['quarter'],parent,nci,eps)
        return self._consume(request,request['url'],parts(request,body=raw),0,None,diagnostic)
    monkeypatch.setattr(t.PeerIncomeHttp,'_download',download)
    return store,calls,rows


def test_eight_normal_full_originals_derive_only_parent_money_without_PE(gourmet_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income,verified_reference_income
    with normal_frame():value=collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    d=verified_reference_income(value['source_record_archive'],ticker=TICKER,observed_at=DAY.isoformat(),today=DAY)
    assert d['net_income_twd']==-197921000 and d['basis']=='reported_cumulative_parent_income'
    assert len(gourmet_environment[1])==8 and 'pe_ttm'not in value
    assert value['reason_basis'].endswith('not_a_published_per_row_cause')

@pytest.mark.parametrize('field,value',[('外國企業註冊地國','TW 中華民國'),('外國企業註冊地國',None),('已發行普通股數或TDR原股發行股數','180000001'),('已發行普通股數或TDR原股發行股數','0180000000'),('特別股','1'),('編制財務報表類型','2'),('公司名稱','美食股份有限公司')])
def test_changed_current_master_rejects_before_any_new_HTTP(gourmet_environment,field,value):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    store,calls,rows=gourmet_environment;rows[-1][field]=value
    with normal_frame(),pytest.raises(ValueError):collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    assert calls==[] and store=={}

@pytest.mark.parametrize('damage',['parent_amount','NCI_source_owner','master_shares','cross_issuer','period','missing_component'])
def test_full_proof_cannot_be_replaced_by_stated_allocation_flags(gourmet_environment,damage):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income,verified_reference_income
    store,calls,rows=gourmet_environment
    with normal_frame():value=collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    proof=deepcopy(value['source_record_archive'])
    if damage=='parent_amount':proof['derived']['net_income_twd']=-186328000
    if damage=='NCI_source_owner':store.clear()
    if damage=='master_shares':rows[-1]['已發行普通股數或TDR原股發行股數']='180000001'
    if damage=='cross_issuer':proof['ticker']='6558.TW'
    if damage=='period':proof['derived']['period_end']='2026-09-30'
    if damage=='missing_component':proof['components'].pop('income:2025Q2')
    assert verified_reference_income(proof,ticker=TICKER,observed_at=DAY.isoformat(),today=DAY)is None


def test_unknown_period_existing_core_or_research_still_cannot_refetch(gourmet_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    store,calls,_=gourmet_environment
    with normal_frame(observe=False),pytest.raises(ValueError):collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    assert not store and not calls
    store['financial_data:'+TICKER]={'source_audit':[{'source':'financial_statements','status':'success','documents':[{'year':2025}]}]}
    before=deepcopy(store)
    with normal_frame(),pytest.raises(ValueError):collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    assert store==before and not calls


def test_normal_consumer_restores_missing_PE_on_owner_loss_and_preserves_other_gaps(gourmet_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    from data_fetch.market_sources.peers import PEER_METRIC_FIELDS
    from data_trust_audit import source_record_count
    from prompt_evidence import prompt_evidence_copy
    with normal_frame():reason=collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    row={k:1.0 for k in PEER_METRIC_FIELDS};row.update(ticker=TICKER,name='美食-KY',pe_ttm=None,pe_applicability_evidence=reason,missing_metrics=['pe_ttm'],metrics_status='partial',metric_sources={k:{'provider':'fixture','observed_at':'2026-06-30'}for k in PEER_METRIC_FIELDS if k!='pe_ttm'})
    reassess_reference_applicability(row,today=DAY)
    assert row['metrics_status']=='complete'and row['pe_ttm']is None
    assert source_record_count('dynamic_peer_metrics',{'dynamic_peer_metrics':[row]})==1
    public=json.dumps(prompt_evidence_copy(row));assert 'raw_response_path'not in public and 'net_income_twd'not in public
    row['pb']=None;reassess_reference_applicability(row,today=DAY)
    assert row['metrics_status']=='partial'and row['missing_metrics']==['pb']
    gourmet_environment[0].clear();reassess_reference_applicability(row,today=DAY)
    assert row['missing_metrics']==['pb','pe_ttm'] or set(row['missing_metrics'])=={'pb','pe_ttm'}


def test_normal_peer_loop_keeps_other_OTC_missing_PE_and_parent_partial(gourmet_environment,monkeypatch):
    from data_fetch.market_sources import peers,official_peer_valuation,taiwan
    from provider_correlation import correlation_scope,source_operation
    from data_fetch.market_sources.ncc_mobile_peer_transport import receipt_observation_scope
    monkeypatch.setattr(peers,'_today',lambda:DAY);monkeypatch.setattr(taiwan,'DataLoader',None)
    monkeypatch.setattr(peers,'load_peer_stock_master',lambda:[])
    monkeypatch.setattr(peers,'resolve_legacy_peer_candidates',lambda *a,**k:([
        {'ticker':s,'name':n,'identity_status':'master_verified','comparison_status':'industry_candidate_only','industry_categories':['觀光事業']}for s,n in [('2723.TW','美食-KY'),('2726.TWO','雅茗-KY')]],{'selection_status':'selected','selection_rejected_reason_counts':{}}))
    monkeypatch.setattr(peers.yf,'Ticker',lambda symbol:type('Quote',(),{'info':{'symbol':symbol,'quoteType':'EQUITY','industry':'Restaurants','trailingPE':None,'grossMargins':.2,'operatingMargins':.1,'profitMargins':.05,'returnOnEquity':.1,'totalRevenue':100,'totalAssets':200,'priceToSalesTrailing12Months':3}})())
    monkeypatch.setattr(official_peer_valuation,'fetch_official_peer_valuation',lambda symbol,**kw:{'metrics':{'pb':1.25},'status':'success','source':official_peer_valuation.PROVIDER,'official_company_name':'美食-KY'if symbol==TICKER else'雅茗-KY','observed_at':DAY.isoformat()})
    with correlation_scope(replace=True,ticker='2727.TW',fetch_id='gourmet-peer-loop'),source_operation('dynamic_peer_metrics','FinMind/yfinance'),receipt_observation_scope(True):
        result=peers.fetch_dynamic_peer_metrics_with_diagnostics('2727.TW','fixture target','Consumer Cyclical','Restaurants',{})
    rows={r['ticker']:r for r in result['peers']}
    assert rows[TICKER]['metrics_status']=='complete'and rows[TICKER]['pe_ttm']is None
    assert rows['2726.TWO']['metrics_status']=='partial'and 'pe_ttm'in rows['2726.TWO']['missing_metrics']
    assert result['audit']['coverage_status']=='partial'and result['audit']['quality_status']=='partial_metrics'


@pytest.fixture
def gourmet_corrected_environment(gourmet_environment,monkeypatch):
    from data_fetch.market_sources import peer_reference_transport as t
    from test_gourmet_correction_notice import corrected_index,notice_body
    old=t.PeerIncomeHttp._download;store,calls,rows=gourmet_environment
    def download(self,request,diagnostic):
        if request['kind']=='correction' or request['kind']=='index'and request['params']['year']==2025:
            calls.append(deepcopy(request));raw=notice_body()if request['kind']=='correction'else corrected_index()
            return self._consume(request,request['url'],parts(request,body=raw),0,None,diagnostic)
        return old(self,request,diagnostic)
    monkeypatch.setattr(t.PeerIncomeHttp,'_download',download)
    return gourmet_environment


def test_published_annex_correction_adds_exact_ninth_complete_owner_bound_original(gourmet_corrected_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income,verified_reference_income
    with normal_frame():value=collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    proof=value['source_record_archive'];assert len(proof['components'])==9
    assert 'correction:2025Q4'in proof['components']
    assert verified_reference_income(proof,ticker=TICKER,observed_at=DAY.isoformat(),today=DAY)['net_income_twd']==-197921000
    calls=gourmet_corrected_environment[1];assert len(calls)==9
    notice=next(i for i,r in enumerate(calls)if r['kind']=='correction')
    assert calls[notice-1]['kind']=='index'and calls[notice-1]['params']['year']==2025

@pytest.mark.parametrize('damage',['owner','request','missing','changed_parent'])
def test_notice_and_other_originals_are_required_on_every_replay(gourmet_corrected_environment,damage):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income,verified_reference_income
    from data_fetch.market_sources.peer_reference_transport import raw_key
    with normal_frame():value=collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    proof=deepcopy(value['source_record_archive']);packet=proof['components']['correction:2025Q4']
    if damage=='owner':gourmet_corrected_environment[0].pop('shared_provider:v1:'+sha256(raw_key(packet['spec']).encode()).hexdigest())
    if damage=='request':packet['spec']['params']['published_action']+='&unexpected=1'
    if damage=='missing':proof['components'].pop('correction:2025Q4')
    if damage=='changed_parent':proof['derived']['net_income_twd']=-186328000
    assert verified_reference_income(proof,ticker=TICKER,observed_at=DAY.isoformat(),today=DAY)is None


def test_a_fresh_changed_notice_does_not_qualify_even_with_complete_HTTP(gourmet_corrected_environment,monkeypatch):
    from data_fetch.market_sources import peer_reference_transport as t
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    from test_gourmet_correction_notice import notice_body
    store,calls,_=gourmet_corrected_environment;old=t.PeerIncomeHttp._download
    def download(self,request,diagnostic):
        if request['kind']=='correction':
            calls.append(deepcopy(request));raw=notice_body().replace('無變動'.encode(),'有變動'.encode(),1)
            return self._consume(request,request['url'],parts(request,body=raw),0,None,diagnostic)
        return old(self,request,diagnostic)
    monkeypatch.setattr(t.PeerIncomeHttp,'_download',download)
    with normal_frame(),pytest.raises(ValueError):collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    assert sum(r['kind']=='correction'for r in calls)==1
    assert not any(r['kind']=='income'for r in calls)


def test_extra_notice_cannot_be_attached_to_an_uncorrected_index(gourmet_environment):
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income,verified_reference_income
    with normal_frame():value=collect_reference_income(TICKER,DAY.isoformat(),today=DAY)
    proof=deepcopy(value['source_record_archive']);proof['components']['correction:2025Q4']={}
    assert verified_reference_income(proof,ticker=TICKER,observed_at=DAY.isoformat(),today=DAY)is None
