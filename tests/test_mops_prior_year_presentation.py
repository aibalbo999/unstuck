"""A prior-year original needs a fresh exact current-year absence proof."""
from copy import deepcopy
from pathlib import Path
import gzip,json,time
import pytest
from test_mops_presentation import harness

ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261018/mops-prior-year-second-look'
E=ROOT/'docs/evidence/source-acquisition/20261018/mops-smallcap-entries'
TICKER='2338.TW'
DATA=json.loads((D/'2338-report-context.json').read_text())

@pytest.fixture
def prior(harness,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    stamp=json.loads((D/'master-receipt.json').read_text())['retrieved_at']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    bodies,calls=harness
    bodies['master']=gzip.decompress((D/'master.csv.gz').read_bytes())
    bodies[TICKER+':index']=gzip.decompress((D/(TICKER+'.index.gz')).read_bytes())
    bodies[TICKER+':material']=gzip.decompress((D/(TICKER+'.material.gz')).read_bytes())
    original=s.download_conference_index;years=[]
    current={'raw':gzip.decompress((E/(TICKER+'.rejected-index.gz')).read_bytes())}
    def index(ticker,year,deadline,diagnostics):
        years.append(year)
        if year==2026:
            old=bodies[TICKER+':index'];bodies[TICKER+':index']=current['raw']
            try:return original(ticker,year=year,deadline=deadline,diagnostics=diagnostics)
            finally:bodies[TICKER+':index']=old
        assert year==2025,'No unbounded year search'
        return original(ticker,year=year,deadline=deadline,diagnostics=diagnostics)
    monkeypatch.setattr(s,'download_conference_index',index)
    return bodies,calls,years,current


def test_prior_year_cold_warm_retains_absence_and_historical_scope(prior):
    from data_fetch.market_sources import mops_presentation as s
    assert s.supports(TICKER) and s.validate_context(DATA,TICKER)
    d={};v=s.fetch_presentation_context(TICKER,diagnostics=d);doc=v['documents'][0]
    assert prior[2]==[2026,2025] and d['http_request_count']==4
    assert doc['page_count']==23 and doc['content_period']=='2025Q3'
    assert doc['event_date']==doc['material_file_date']=='2025-12-29'
    assert doc['native_text_coverage']=='complete' and not doc['full_content_coverage_verified']
    assert all(t in doc['period_scope_caution']for t in ('前一年','歷史','商業','累計','模板'))
    assert s.verify_context(v,TICKER)
    prior[1].clear();prior[2].clear();d={};warm=s.fetch_presentation_context(TICKER,diagnostics=d)
    assert d['cache_hit'] and d['http_request_count']==0 and not prior[1] and not prior[2]
    assert warm['fetched_at_epoch']==v['fetched_at_epoch']

@pytest.mark.parametrize('change',['missing_absence','absence_request','prior_request','absence_receipt','projection'])
def test_unproven_or_tampered_prior_year_context_rejected(prior,change):
    from data_fetch.market_sources import mops_presentation as s
    v=s.fetch_presentation_context(TICKER);proof=v['mops_material_receipt']
    if change=='missing_absence':proof.pop('absence_current_index')
    elif change=='absence_request':proof['absence_current_request']=deepcopy(proof['index_request'])
    elif change=='prior_request':proof['index_request']=deepcopy(proof['absence_current_request'])
    elif change=='absence_receipt':proof['absence_current_index']['raw_response_sha256']='0'*64
    else:v['documents'][0]['period_scope_caution']='current-year results'
    assert not s.verify_context(v,TICKER)


def test_current_absence_must_remain_fresh_at_final_handoff(prior,monkeypatch):
    from data_fetch.market_sources import mops_presentation as s
    v=s.fetch_presentation_context(TICKER);proof=v['mops_material_receipt'];now=time.time()
    proof['absence_current_index']['fresh_until_epoch']=now+2
    monkeypatch.setattr(time,'time',lambda:now+3)
    assert not s._originals_current_at_handoff(proof)

@pytest.mark.parametrize('change',['extra_markup','challenge','unpublished_current'])
def test_no_fallback_for_ambiguous_or_not_yet_published_current_page(prior,change):
    from data_fetch.market_sources import mops_presentation as s
    from search_provider_runtime import SourceResponseError
    if change=='extra_markup':prior[3]['raw']+=b'<table>other data</table>'
    elif change=='challenge':prior[3]['raw']='<html><body>captcha 查無資料</body></html>'.encode()
    else:prior[3]['raw']=prior[0][TICKER+':index'].replace(b'2025',b'2026').replace(b'114/',b'115/')
    with pytest.raises((SourceResponseError,ValueError)):s.fetch_presentation_context(TICKER)
    assert prior[2]==[2026]


def test_previous_year_selection_age_and_calendar_are_bounded():
    from mops_previous_year import eligible_previous
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now=datetime(2026,10,18,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    valid={'event_date':'2025-12-29','event_end_date':'2025-12-29'}
    assert eligible_previous(valid,2026,now)
    assert not eligible_previous({'event_date':'2025-01-01','event_end_date':'2025-01-01'},2026,now)
    assert not eligible_previous({'event_date':'2026-01-01','event_end_date':'2026-01-01'},2026,now)
    assert not eligible_previous(valid,2027,now)

@pytest.mark.parametrize('change',['cover','issuer','financial_period','comparison','license'])
def test_native_identity_period_and_ownership_notice_bound(prior,monkeypatch,change):
    from data_fetch.market_sources import mops_presentation as s
    from mops_published_materials import select_published_material
    selected=select_published_material(prior[0][TICKER+':index'],TICKER,as_of_epoch=time.time(),company_name='光罩')
    native=json.loads((D/(TICKER+'.native.json')).read_text())
    for p in native['pages']:
        if change=='cover' and p['page_number']==1:p['text']=p['text'].replace('Dec.29','Dec.28')
        elif change=='issuer':p['text']=p['text'].replace('TAIWAN MASK CORPORATION','OTHER COMPANY')
        elif change=='financial_period':p['text']=p['text'].replace('3Q 25','3Q 26')
        elif change=='comparison':p['text']=p['text'].replace('3Q 24','3Q 23')
        elif change=='license':p['text']=p['text'].replace('Without the permission of the company','With permission')
    monkeypatch.setattr(s,'extract_pdf_pages',lambda *a,**k:native)
    with pytest.raises(ValueError):s.native_material(prior[0][TICKER+':material'],selected,time.monotonic()+15)


def test_normal_provider_and_roles_keep_history_and_rights(prior):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_presentation_prompt import presentation_prompt_context
    cold=EarningsCallProvider().fetch(FetchRequest.from_ticker(TICKER),{'data':deepcopy(DATA)})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==4
    for role in (3,5,12):
        doc=presentation_prompt_context(cold.value,role)['documents'][0]
        assert doc['content_period']=='2025Q3' and '前一年' in doc['period_scope_caution']
        assert not doc['financial_statement_complete'] and not doc['commercial_reuse_permission_verified']
