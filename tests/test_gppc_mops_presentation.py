"""GPPC date and cumulative financial boundaries through the common workflow."""
from copy import deepcopy
from pathlib import Path
import gzip,json,time
import pytest
from test_mops_presentation import harness

D=Path(__file__).parents[1]/'docs/evidence/source-acquisition/20261018/mops-traditional-entries'
TICKER='1312.TW'
ROW=next(x for x in json.loads((D/'actual-report-contexts.json').read_text())if x['ticker']==TICKER)
DATA={k:deepcopy(ROW[k])for k in ('ticker','company_name','raw_company_name')}
DATA.update(instrument_type='EQUITY',company_identity=deepcopy(ROW['identity']))

@pytest.fixture
def gppc(harness,monkeypatch):
    stamp=json.loads((D/'master-receipt.json').read_text())['retrieved_at']+1
    monkeypatch.setattr(time,'time',lambda:stamp)
    harness[0]['master']=gzip.decompress((D/'master.csv.gz').read_bytes())
    for kind in ('index','material'):
        harness[0][TICKER+':'+kind]=gzip.decompress((D/(TICKER+'.'+kind+'.gz')).read_bytes())
    return harness


def test_original_cold_warm_and_period_tamper(gppc):
    from data_fetch.market_sources import mops_presentation as s
    assert s.supports(TICKER) and s.validate_context(DATA,TICKER)
    d={};v=s.fetch_presentation_context(TICKER,diagnostics=d);doc=v['documents'][0]
    assert doc['page_count']==29 and doc['content_period']=='2026H1'
    assert doc['event_date']==doc['material_file_date']=='2026-09-23'
    assert doc['native_text_coverage']=='complete' and d['http_request_count']==3
    assert not doc['full_content_coverage_verified'] and not doc['financial_statement_complete']
    assert all(x in doc['period_scope_caution']for x in ('H1','Q3(E)','FY'))
    assert s.verify_context(v,TICKER)
    bad=deepcopy(v);bad['documents'][0]['content_period']='2026Q2'
    assert not s.verify_context(bad,TICKER)
    gppc[1].clear();d={};warm=s.fetch_presentation_context(TICKER,diagnostics=d)
    assert not gppc[1] and d['cache_hit'] and d['http_request_count']==0
    assert warm['fetched_at_epoch']==v['fetched_at_epoch']


@pytest.mark.parametrize('change',['issuer','cover_date','current_period','comparison_period','ambiguous_period','disclaimer','empty_page'])
def test_native_rejects_invalid_identity_dates_periods(gppc,monkeypatch,change):
    from data_fetch.market_sources import mops_presentation as s
    from mops_published_materials import select_published_material
    selected=select_published_material(gppc[0][TICKER+':index'],TICKER,as_of_epoch=time.time(),company_name='國喬')
    native=json.loads((D/(TICKER+'.native.json')).read_text())
    if change=='issuer':native['pages'][0]['text']=native['pages'][0]['text'].replace('GRAND PACIFIC PETROCHEMICAL CORPORATION','OTHER ISSUER')
    elif change=='cover_date':native['pages'][0]['text']=native['pages'][0]['text'].replace('1 1 5','1 1 4')
    elif change=='current_period':native['pages'][24]['text']=native['pages'][24]['text'].replace('H126','H127')
    elif change=='comparison_period':native['pages'][24]['text']=native['pages'][24]['text'].replace('H125','H124')
    elif change=='ambiguous_period':native['pages'][24]['text']+='\nConsolidated Statements of Income (NT$ M) Item H126 H125 Diff.'
    elif change=='disclaimer':native['pages'][2]['text']=native['pages'][2]['text'].replace('The forward-looking statements contained in this presentation','Past observations')
    else:native['pages'][23]['text']='';native['empty_pages']=[24];native['coverage_status']='partial'
    monkeypatch.setattr(s,'extract_pdf_pages',lambda *a,**k:native)
    with pytest.raises(ValueError):s.native_material(gppc[0][TICKER+':material'],selected,time.monotonic()+15)


def test_provider_and_roles_preserve_cumulative_and_forecast_boundaries(gppc):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_presentation_prompt import presentation_prompt_context
    request=FetchRequest.from_ticker(TICKER)
    cold=EarningsCallProvider().fetch(request,{'data':deepcopy(DATA)})
    assert cold.audit['status']=='success' and cold.audit['http_request_count']==3
    warm=EarningsCallProvider().fetch(request,{'data':deepcopy(DATA)})
    assert warm.audit['status']=='skipped_fresh_cache'
    for role in (3,5,12):
        doc=presentation_prompt_context(cold.value,role)['documents'][0]
        assert doc['content_period']=='2026H1' and 'Q3(E)' in doc['period_scope_caution']
        assert not doc['financial_statement_complete'] and not doc['full_content_coverage_verified']


def test_observed_alias_keeps_company_identity_boundary(gppc):
    from data_fetch.market_sources import mops_presentation as s
    assert s.validate_context(DATA,TICKER)
    bad=deepcopy(DATA);bad['company_identity']['official_ubn']='00000000'
    assert not s.validate_context(bad,TICKER)
    bad=deepcopy(DATA);bad['company_identity']['allowed_aliases'].append('OTHER GPPC')
    assert not s.validate_context(bad,TICKER)
