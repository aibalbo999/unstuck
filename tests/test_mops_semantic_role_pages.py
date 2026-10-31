"""Issuer-qualified whole pages preserve period, ownership, and chart boundaries."""
from copy import deepcopy
from pathlib import Path
import gzip,json,time,re
import pytest
from test_mops_presentation import harness

D=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261018/mops-next-five-entries'
ROWS={x['ticker']:x for x in json.loads((D/'actual-report-contexts.json').read_text())}
EXPECTED={'6282.TW':(16,'2026Q2',{3:[2,10,11,13],5:[2,5,6],12:[2,5,6]}),
          '9945.TW':(34,'2026Q1',{3:[2,8],5:[2,3,13],12:[2,33]}),
          '2441.TW':(18,'2026H1',{3:[2,5,6,7],5:[2,12,13],12:[2,15,16]})}
def data(ticker):return {k:deepcopy(ROWS[ticker][k])for k in ('ticker','instrument_type','company_name','raw_company_name','company_identity')}

@pytest.fixture
def semantic(harness,monkeypatch):
    stamp=json.loads((D/'master-receipt.json').read_text())['retrieved_at']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    harness[0]['master']=gzip.decompress((D/'master.csv.gz').read_bytes())
    for ticker in EXPECTED:
        for kind in ('index','material'):harness[0][ticker+':'+kind]=gzip.decompress((D/(ticker+'.'+kind+'.gz')).read_bytes())
    return harness

@pytest.mark.parametrize('ticker',EXPECTED)
def test_real_original_full_storage_whole_qualified_roles_and_warm_cache(semantic,ticker):
    from data_fetch.market_sources import mops_presentation as s
    from conference_presentation_prompt import presentation_prompt_context
    assert s.supports(ticker) and s.validate_context(data(ticker),ticker)
    d={};v=s.fetch_presentation_context(ticker,diagnostics=d);doc=v['documents'][0]
    count,period,roles=EXPECTED[ticker]
    assert doc['page_count']==count and len(doc['pages'])==count and doc['content_period']==period
    assert d['http_request_count']==3 and doc['native_text_coverage']=='complete'
    assert not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
    assert s.verify_context(v,ticker)
    before=deepcopy(v)
    for role,numbers in roles.items():
        item=presentation_prompt_context(v,role)['documents'][0]
        assert [p['page_number']for p in item['pages']]==numbers
        assert all(not p['content_truncated']for p in item['pages'])
        assert item['selection_policy']=='mops-qualified-whole-pages-v1'
        assert item['period_scope_caution']==doc['period_scope_caution']
        assert item['projection_excluded_pages']==doc['projection_excluded_pages']
        assert not item['commercial_reuse_permission_verified']
    assert v==before
    semantic[1].clear();d={};warm=s.fetch_presentation_context(ticker,diagnostics=d)
    assert d['cache_hit'] and d['http_request_count']==0 and not semantic[1]
    assert warm['fetched_at_epoch']==v['fetched_at_epoch']

@pytest.mark.parametrize('ticker',EXPECTED)
@pytest.mark.parametrize('change',['allowlist','missing_allowlist','context_ticker'])
def test_prompt_cannot_trust_caller_supplied_role_metadata(semantic,ticker,change):
    from data_fetch.market_sources import mops_presentation as s
    from conference_presentation_prompt import presentation_prompt_context
    v=s.fetch_presentation_context(ticker)
    if change=='allowlist':v['documents'][0]['role_page_allowlist']['3'].append({'6282.TW':8,'9945.TW':22,'2441.TW':9}[ticker])
    elif change=='missing_allowlist':v['documents'][0].pop('role_page_allowlist')
    else:v['ticker']='2338.TW'
    assert not presentation_prompt_context(v,3).get('documents')

@pytest.mark.parametrize('ticker',EXPECTED)
@pytest.mark.parametrize('change',['issuer','binding','period','empty_page'])
def test_native_identity_financial_periods_and_coverage_fail_closed(semantic,monkeypatch,ticker,change):
    from data_fetch.market_sources import mops_presentation as s
    from mops_published_materials import select_published_material
    selected=select_published_material(semantic[0][ticker+':index'],ticker,as_of_epoch=time.time(),company_name=ROWS[ticker]['company_identity']['official_name'])
    native=json.loads((D/(ticker+'.native.json')).read_text())
    for p in native['pages']:
        if change=='issuer':
            p['text']=re.sub(r'Acbel Polytech Inc\.|RUENTEX DEVELOPMENT|Greatek Electronics','OTHER ISSUER',p['text'],flags=re.I)
        elif change=='binding':
            p['text']=p['text'].replace('6282.TW','9999.TW').replace('9945TW','9999TW').replace('www.greatek.com.tw','example.org')
        elif change=='period':
            p['text']=p['text'].replace('2Q26 Results Overview','2Q27 Results Overview').replace('2026Q1 Financial Report','2027Q1 Financial Report').replace('First Half of Year 2026','First Half of Year 2027')
    if change=='empty_page':native['empty_pages']=[3];native['pages'][2]['text']='';native['coverage_status']='partial'
    monkeypatch.setattr(s,'extract_pdf_pages',lambda *a,**k:native)
    with pytest.raises(ValueError):s.native_material(semantic[0][ticker+':material'],selected,time.monotonic()+15)

@pytest.mark.parametrize('ticker',EXPECTED)
def test_normal_provider_routes_and_one_body_count(semantic,ticker):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    request=FetchRequest.from_ticker(ticker)
    cold=EarningsCallProvider().fetch(request,{'data':data(ticker)})
    assert cold.audit['status']=='success' and cold.audit['record_count']==1 and cold.audit['http_request_count']==3
    warm=EarningsCallProvider().fetch(request,{'data':data(ticker)})
    assert warm.audit['status']=='skipped_fresh_cache' and warm.audit['http_request_count']==0


@pytest.mark.parametrize('bad_ticker',[{},[],None,42])
def test_malformed_context_identity_cannot_crash_or_project_qualified_pages(bad_ticker):
    from conference_presentation_prompt import presentation_prompt_context
    context={'ticker':bad_ticker,'documents':[{'ticker':'6282.TW','source':'MOPS published presentation',
             'document_kind':'presentation','pages':[{'page_number':1,'text':'revenue market strategy'}]}]}
    assert not presentation_prompt_context(context,3).get('documents')


def test_noninteger_role_is_not_a_qualified_role(semantic):
    from data_fetch.market_sources import mops_presentation as s
    from conference_presentation_prompt import presentation_prompt_context
    value=s.fetch_presentation_context('6282.TW')
    assert not presentation_prompt_context(value,3.0).get('documents')


@pytest.mark.parametrize('ticker',EXPECTED)
def test_new_year_uses_proven_previous_year_and_retains_history_in_roles(semantic,monkeypatch,ticker):
    import csv,io
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from data_fetch.market_sources import mops_presentation as s
    from conference_presentation_prompt import presentation_prompt_context
    reader=csv.DictReader(io.StringIO(semantic[0]['master'].decode('utf-8-sig')))
    rows=list(reader);stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=reader.fieldnames);writer.writeheader()
    for row in rows:row['出表日期']='1160102'
    writer.writerows(rows);semantic[0]['master']=stream.getvalue().encode()
    stamp=datetime(2027,1,2,12,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monkeypatch.setattr(time,'time',lambda:stamp)
    empty=gzip.decompress((D.parent/'mops-smallcap-entries/2338.TW.rejected-index.gz').read_bytes())
    original=s.download_conference_index;years=[]
    def index(requested,year,deadline,diagnostics):
        years.append(year)
        if year==2027:
            old=semantic[0][ticker+':index'];semantic[0][ticker+':index']=empty
            try:return original(requested,year=year,deadline=deadline,diagnostics=diagnostics)
            finally:semantic[0][ticker+':index']=old
        assert year==2026
        return original(requested,year=year,deadline=deadline,diagnostics=diagnostics)
    monkeypatch.setattr(s,'download_conference_index',index)
    diagnostic={};value=s.fetch_presentation_context(ticker,diagnostics=diagnostic)
    assert years==[2027,2026] and diagnostic['http_request_count']==4
    assert value['documents'][0]['content_period']==EXPECTED[ticker][1]
    assert s.verify_context(value,ticker)
    for role in (3,5,12):
        doc=presentation_prompt_context(value,role)['documents'][0]
        assert '前一年' in doc['period_scope_caution'] and '歷史' in doc['period_scope_caution']
        assert [p['page_number']for p in doc['pages']]==EXPECTED[ticker][2][role]
