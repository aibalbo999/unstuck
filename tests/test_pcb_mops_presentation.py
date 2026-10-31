"""Qualified Flexium/Foxconn originals preserve mixed periods and image gaps."""
from copy import deepcopy
from pathlib import Path
import gzip,json,time,re
import pytest
from test_mops_presentation import harness

D=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261017/mops-pcb-entries'
CONFIG={'2354.TW':('鴻準','Foxconn Technology Co., Ltd.','FOXCONN TECH CO','23707801',32,'2026Q2'),
        '6269.TW':('台郡','Flexium Interconnect, Inc.','FLEXIUM INTERCONNECT INC','16347324',8,'2026Q2')}
def data(ticker):
    short,en,quote,ubn,*_=CONFIG[ticker]
    return {'ticker':ticker,'instrument_type':'EQUITY','company_name':short+' / '+en,'raw_company_name':en,
            'company_identity':{'ticker':ticker,'stock_id':ticker.split('.')[0],'official_name':short,
             'official_ubn':ubn,'allowed_aliases':[short,en,quote,ticker,ticker.split('.')[0]],
             'english_names':[en,quote],'forbidden_aliases':[]}}

@pytest.fixture
def pcb(harness,monkeypatch):
    stamp=json.loads((D/'master-receipt.json').read_text())['retrieved_at']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    harness[0]['master']=gzip.decompress((D/'master.csv.gz').read_bytes())
    for ticker in CONFIG:
        for kind in ('index','material'):
            harness[0][ticker+':'+kind]=gzip.decompress((D/(ticker+'.'+kind+'.gz')).read_bytes())
    return harness

@pytest.mark.parametrize('ticker',CONFIG)
def test_cold_warm_original_identity_and_projection(pcb,ticker):
    from data_fetch.market_sources import mops_presentation as s
    assert s.supports(ticker) and s.validate_context(data(ticker),ticker)
    d={};v=s.fetch_presentation_context(ticker,diagnostics=d);doc=v['documents'][0]
    assert doc['page_count']==CONFIG[ticker][-2] and doc['content_period']==CONFIG[ticker][-1]
    assert d['http_request_count']==3 and doc['native_text_coverage']=='complete'
    assert not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
    assert 'Q2' in doc['period_scope_caution'] and 'H1' in doc['period_scope_caution']
    if ticker=='2354.TW':
        assert 'Q3' in doc['period_scope_caution']
        assert [x['page_number']for x in doc['known_native_text_omissions']]==[13,22,23,24,25,26,30]
    else:assert 'Rafael' in doc['period_scope_caution'] and '8 of 7' in doc['period_scope_caution']
    assert s.verify_context(v,ticker)
    changed=deepcopy(v);changed['documents'][0]['content_period']='2026Q3'
    assert not s.verify_context(changed,ticker)
    pcb[1].clear();d={};warm=s.fetch_presentation_context(ticker,diagnostics=d)
    assert not pcb[1] and d['cache_hit'] and d['http_request_count']==0
    assert warm['fetched_at_epoch']==v['fetched_at_epoch']

@pytest.mark.parametrize('ticker',CONFIG)
@pytest.mark.parametrize('change',['issuer','period','contact','empty_page','financial_scope'])
def test_native_binding_rejects_changed_evidence(pcb,monkeypatch,ticker,change):
    from data_fetch.market_sources import mops_presentation as s
    from mops_published_materials import select_published_material
    selected=select_published_material(pcb[0][ticker+':index'],ticker,as_of_epoch=time.time(),company_name=CONFIG[ticker][0])
    native=json.loads((D/(ticker+'.native.json')).read_text())
    if change=='issuer':native['pages'][0]['text']='UNRELATED ISSUER'
    elif change=='period':
        for page in native['pages']:
            page['text']=page['text'].replace('2026Q2','2027Q2').replace('2Q 2026 Earnings Conference','2Q 2027 Earnings Conference')
    elif change=='contact':
        for page in native['pages']:
            page['text']=page['text'].replace('2354.TW','9999.TW').replace('ir@flexium.com.tw','ir@example.org')
    elif change=='empty_page':native['empty_pages']=[3];native['coverage_status']='partial';native['pages'][2]['text']=''
    else:
        for page in native['pages']:
            page['text']=page['text'].replace('unaudited and unreviewed information','audited data').replace('Consolidated Income Statement (YTD)','Annual data')
    monkeypatch.setattr(s,'extract_pdf_pages',lambda *a,**k:native)
    with pytest.raises(ValueError):s.native_material(pcb[0][ticker+':material'],selected,time.monotonic()+15)

@pytest.mark.parametrize('ticker',CONFIG)
def test_provider_and_role_prompts_keep_cautions(pcb,ticker):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_presentation_prompt import presentation_prompt_context
    request=FetchRequest.from_ticker(ticker)
    cold=EarningsCallProvider().fetch(request,{'data':data(ticker)})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==3
    warm=EarningsCallProvider().fetch(request,{'data':data(ticker)})
    assert warm.audit['status']=='skipped_fresh_cache'
    for role in (3,5,12):
        doc=presentation_prompt_context(cold.value,role)['documents'][0]
        assert doc['content_period']=='2026Q2' and 'H1' in doc['period_scope_caution']
        assert doc['known_native_text_omissions']==cold.value['documents'][0]['known_native_text_omissions']
        assert not doc['full_content_coverage_verified']

@pytest.mark.parametrize('ticker',CONFIG)
def test_cross_company_alias_not_allowed(pcb,ticker):
    from data_fetch.market_sources import mops_presentation as s
    d=data(ticker);assert s.validate_context(d,ticker)
    d['company_identity']['official_ubn']='00000000';assert not s.validate_context(d,ticker)
