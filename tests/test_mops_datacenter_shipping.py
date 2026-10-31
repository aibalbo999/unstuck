"""Original-bound quarterly tables and whole-page role views for two issuers."""
from copy import deepcopy
from pathlib import Path
import gzip,json,time
import pytest
from test_mops_presentation import harness
P=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261018/mops-following-entries'
CONTEXTS=json.loads((P.parent/'runtime-recovery-0627/candidate-report-gaps.json').read_text())
DATA={row['ticker']:row['identity']for row in CONTEXTS}
ROLES={'6669.TW':{3:[1,2,3,4,5],5:[1,2],12:[1,2]},'2606.TW':{3:[4,28],5:[3,28],12:[10,27,28]}}
@pytest.fixture
def originals(harness,monkeypatch):
    monkeypatch.setattr(time,'time',lambda:json.loads((P/'master-receipt.json').read_text())['retrieved_at']+1)
    harness[0]['master']=gzip.decompress((P/'master.csv.gz').read_bytes())
    for ticker in ROLES:
        for kind in ('index','material'):harness[0][ticker+':'+kind]=gzip.decompress((P/(ticker+'.'+kind+'.gz')).read_bytes())
    return harness

@pytest.mark.parametrize('ticker',ROLES)
def test_originals_whole_roles_keep_period_and_permission_boundaries(originals,ticker):
    from data_fetch.market_sources import mops_presentation as s
    from conference_presentation_prompt import presentation_prompt_context
    assert s.supports(ticker) and s.validate_context(DATA[ticker],ticker)
    value=s.fetch_presentation_context(ticker);doc=value['documents'][0]
    assert doc['content_period']=='2026Q2' and doc['native_text_coverage']=='complete'
    assert doc['page_count']==(6 if ticker=='6669.TW' else 29)
    assert not doc['full_content_coverage_verified'] and not doc['commercial_reuse_permission_verified']
    assert s.verify_context(value,ticker)
    from mops_body_cache import body_ready
    assert body_ready(ticker)
    for role,numbers in ROLES[ticker].items():
        item=presentation_prompt_context(value,role)['documents'][0]
        assert [x['page_number']for x in item['pages']]==numbers
        assert all(not x['content_truncated']for x in item['pages'])
        assert item['period_scope_caution']==doc['period_scope_caution']
        if ticker=='6669.TW':assert 'Any redistribution or reproduction' in item['pages'][0]['text']
    assert ('Q1-Q2' in doc['period_scope_caution']) if ticker=='6669.TW' else ('Q3' in doc['period_scope_caution'] and 'Q2' in doc['period_scope_caution'])
    originals[1].clear();warm=s.fetch_presentation_context(ticker)
    assert warm['fetched_at_epoch']==value['fetched_at_epoch'] and not originals[1]

@pytest.mark.parametrize('ticker',ROLES)
@pytest.mark.parametrize('change',['issuer','financial_year','cover_date','notice','empty_page','cover_scope','units'])
def test_original_identity_period_notice_and_completeness_fail_closed(originals,monkeypatch,ticker,change):
    from data_fetch.market_sources import mops_presentation as s
    from mops_published_materials import select_published_material
    assert s.supports(ticker)
    selected=select_published_material(originals[0][ticker+':index'],ticker,as_of_epoch=time.time(),company_name=s.PROFILES[ticker]['short'])
    native=json.loads((P/(ticker+'.native.json')).read_text())
    if change=='issuer':native['pages'][0]['text']=native['pages'][0]['text'].replace(s.PROFILES[ticker]['native_name'],'Other Issuer')
    elif change=='financial_year':
        for page in native['pages']:page['text']=page['text'].replace('Income Statement 2026 Q2','Income Statement 2027 Q2').replace('2026Q2 results highlights','2027Q2 results highlights')
    elif change=='cover_date':native['pages'][0]['text']=native['pages'][0]['text'].replace('August 7, 2026','August 7, 2027').replace('Sep 16, 2026','Sep 17, 2026')
    elif change=='notice':
        for page in native['pages']:page['text']=page['text'].replace('express written permission','unknown').replace('This presentation contains forward-looking statements.','unknown')
    elif change=='cover_scope':native['pages'][0]['text']=native['pages'][0]['text'].replace('2026 Q2 Financial Results','2026 Q3 Financial Results').replace('2026 年第 3 季法說會','2026 年第 4 季法說會')
    elif change=='units':
        for page in native['pages']:page['text']=page['text'].replace('NT$ millions','USD thousands').replace('NT$m','USDk')
    else:native['pages'][2]['text']='';native.update(empty_pages=[3],coverage_status='partial')
    monkeypatch.setattr(s,'extract_pdf_pages',lambda *a,**k:native)
    with pytest.raises(ValueError):s.native_material(originals[0][ticker+':material'],selected,time.monotonic()+10)

@pytest.mark.parametrize('ticker',ROLES)
def test_canonical_provider_uses_new_original_and_counts_warm_as_cache(originals,ticker):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker(ticker),{'data':DATA[ticker]})
    assert result.audit['record_count']==1 and result.audit['status']=='success'
    again=EarningsCallProvider().fetch(FetchRequest.from_ticker(ticker),{'data':DATA[ticker]})
    assert again.audit['cache_hit'] and again.audit['http_request_count']==0


@pytest.mark.parametrize('ticker',ROLES)
def test_prior_year_fallback_preserves_history_and_role_restrictions(originals,monkeypatch,ticker):
    import csv,io
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from data_fetch.market_sources import mops_presentation as s
    from conference_presentation_prompt import presentation_prompt_context
    reader=csv.DictReader(io.StringIO(originals[0]['master'].decode('utf-8-sig')))
    rows=list(reader);stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=reader.fieldnames);writer.writeheader()
    for row in rows:row['出表日期']='1160102'
    writer.writerows(rows);originals[0]['master']=stream.getvalue().encode()
    stamp=datetime(2027,1,2,12,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monkeypatch.setattr(time,'time',lambda:stamp)
    empty=gzip.decompress((P.parent/'mops-smallcap-entries/2338.TW.rejected-index.gz').read_bytes())
    original=s.download_conference_index;years=[]
    def index(requested,year,deadline,diagnostics):
        years.append(year)
        if year==2027:
            prior=originals[0][ticker+':index'];originals[0][ticker+':index']=empty
            try:return original(requested,year=year,deadline=deadline,diagnostics=diagnostics)
            finally:originals[0][ticker+':index']=prior
        assert year==2026
        return original(requested,year=year,deadline=deadline,diagnostics=diagnostics)
    monkeypatch.setattr(s,'download_conference_index',index)
    value=s.fetch_presentation_context(ticker)
    assert years==[2027,2026] and s.verify_context(value,ticker)
    for role in (3,5,12):
        item=presentation_prompt_context(value,role)['documents'][0]
        assert '前一年' in item['period_scope_caution'] and '歷史' in item['period_scope_caution']
        assert [p['page_number']for p in item['pages']]==ROLES[ticker][role]
