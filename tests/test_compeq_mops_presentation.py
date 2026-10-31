"""Qualified Compeq originals, period boundaries, and normal provider routing."""
from copy import deepcopy
import gzip
import json
import re
from pathlib import Path
import time
import pytest
from test_mops_presentation import harness

ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261017/mops-manufacturing-entries'
TICKER='2313.TW'
DATA={'ticker':TICKER,'instrument_type':'EQUITY','company_name':'華通 / Compeq Manufacturing Co., Ltd.',
      'raw_company_name':'COMPEQ MFG CO', 'company_identity':{'ticker':TICKER,'stock_id':'2313',
      'official_name':'華通','legal_name':'華通電腦股份有限公司','official_ubn':'04401392',
      'allowed_aliases':['華通',TICKER,'2313','華通 / Compeq Manufacturing Co., Ltd.','COMPEQ MFG CO'],
      'english_names':['Compeq Manufacturing Co., Ltd.','COMPEQ MFG CO'],'forbidden_aliases':[]}}

@pytest.fixture
def compeq(harness,monkeypatch):
    stamp=json.loads((D/'master-receipt.json').read_text())['retrieved_at']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    bodies,calls=harness
    bodies['master']=gzip.decompress((D/'master.csv.gz').read_bytes())
    for kind in ('index','material'):bodies[TICKER+':'+kind]=gzip.decompress((D/(TICKER+'.'+kind+'.gz')).read_bytes())
    return bodies,calls


def test_real_original_cold_warm_and_tamper(compeq):
    from data_fetch.market_sources import mops_presentation as s
    assert s.supports(TICKER) and s.validate_context(DATA,TICKER)
    d={};v=s.fetch_presentation_context(TICKER,diagnostics=d);doc=v['documents'][0]
    assert d['http_request_count']==3 and d['mops_material_originals_verified']
    assert doc['page_count']==14 and doc['native_text_coverage']=='complete'
    assert doc['content_period']=='2026H1' and doc['event_date']=='2026-09-04'
    assert doc['material_file_date']=='2026-08-18'
    assert 'H1' in doc['period_scope_caution'] and 'Q2' in doc['period_scope_caution']
    assert not doc['financial_statement_complete'] and not doc['full_content_coverage_verified']
    assert s.verify_context(v,TICKER)
    forged=deepcopy(v);forged['documents'][0]['content_period']='2026Q2'
    assert not s.verify_context(forged,TICKER)
    compeq[1].clear();d={};warm=s.fetch_presentation_context(TICKER,diagnostics=d)
    assert not compeq[1] and d['http_request_count']==0 and d['cache_hit']
    assert warm['fetched_at_epoch']==v['fetched_at_epoch']


@pytest.mark.parametrize(('field','wrong'),[('official_ubn','99999999'),('ticker','2313.TWO'),('legal_name','別家公司股份有限公司')])
def test_wrong_issuer_context_is_rejected(compeq,field,wrong):
    from data_fetch.market_sources import mops_presentation as s
    data=deepcopy(DATA);data['company_identity'][field]=wrong
    assert not s.validate_context(data,TICKER)


@pytest.mark.parametrize('change',['stock_code','cover_month','future_period','ambiguous_period','disclaimer','empty_page'])
def test_native_identity_period_and_coverage_fail_closed(compeq,monkeypatch,change):
    from data_fetch.market_sources import mops_presentation as s
    from mops_published_materials import select_published_material
    selected=select_published_material(compeq[0][TICKER+':index'],TICKER,as_of_epoch=time.time(),company_name='華通')
    native=json.loads((D/(TICKER+'.native.json')).read_text())
    if change=='stock_code':native['pages'][0]['text']=native['pages'][0]['text'].replace('2313.TW','2314.TW')
    elif change=='cover_month':native['pages'][0]['text']=native['pages'][0]['text'].replace('8 月','9 月')
    elif change=='future_period':
        for p in native['pages']:p['text']=p['text'].replace('2026H1','2027H1')
    elif change=='ambiguous_period':native['pages'][7]['text']+='\nCompeq Revenue and Gross Margin from 2022 to 2025H1'
    elif change=='disclaimer':native['pages'][1]['text']=re.sub(r'not been\s+reviewed by independent accountants','fully audited',native['pages'][1]['text'])
    else:native['empty_pages']=[4];native['coverage_status']='partial';native['pages'][3]['text']=''
    monkeypatch.setattr(s,'extract_pdf_pages',lambda *a,**k:native)
    with pytest.raises(ValueError):s.native_material(compeq[0][TICKER+':material'],selected,time.monotonic()+15)


def test_normal_provider_and_roles_keep_scope(compeq):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_presentation_prompt import presentation_prompt_context
    request=FetchRequest.from_ticker(TICKER)
    cold=EarningsCallProvider().fetch(request,{'data':deepcopy(DATA)})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==3
    warm=EarningsCallProvider().fetch(request,{'data':deepcopy(DATA)})
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0
    for role in (3,5,12):
        doc=presentation_prompt_context(cold.value,role)['documents'][0]
        assert doc['content_period']=='2026H1' and 'Q2' in doc['period_scope_caution']
        assert not doc['financial_statement_complete'] and not doc['full_content_coverage_verified']


def test_observed_quote_alias_keeps_identity_boundary(compeq):
    from data_fetch.market_sources import mops_presentation as s
    data=deepcopy(DATA)
    data['company_identity']['allowed_aliases'].append('COMPEQ MANUFACTURING')
    data['company_identity']['english_names'].append('COMPEQ MANUFACTURING')
    assert s.validate_context(data,TICKER)
    data['company_identity']['allowed_aliases'].append('UNRELATED MANUFACTURING')
    assert not s.validate_context(data,TICKER)
