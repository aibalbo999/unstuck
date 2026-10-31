"""Actual default registry routing, including honest unknown revision failure."""
import asyncio
from test_pcsc_conference import harness, INDEX, PDF


def acquire():
    from data_fetch import StockDataService
    from data_fetch.types import FetchRequest
    return asyncio.run(StockDataService().fetch_source_async(
        FetchRequest.from_ticker('2912.TW'),'earnings_call',context={'data':{
            'ticker':'2912.TW','stock_id':'2912','quote_type':'EQUITY',
            'company_name':'統一超','company_identity':{'stock_id':'2912','quoteType':'EQUITY'}}}))


def test_default_registry_follows_new_same_row_path_and_preserves_partial(harness):
    from data_fetch.market_sources.pcsc_conference import PROVIDER
    newpdf=PDF.replace('/262/','/263/')
    harness[0][INDEX]=harness[0][INDEX].replace(b'/262/',b'/263/').replace(b'2026-09-17',b'2026-10-15')
    harness[0][newpdf]=harness[0][PDF]
    result=acquire()
    value=result.data['earnings_call'];doc=value['documents'][0]
    assert doc['url']==newpdf and doc['event_date']=='2026-10-15'
    assert doc['coverage_status']=='partial' and doc['financial_statement_complete'] is False
    assert doc['page_count']==22 and 19 in doc['projection_excluded_pages']
    audits=[a for a in result.source_audit if a.get('provider')==PROVIDER]
    assert len(audits)==1 and audits[0]['record_count']==1
    assert audits[0]['status']=='success' and audits[0]['http_request_count']==4
    assert audits[0]['coverage_status']=='qualified_partial_presentation'


def test_default_registry_holds_unknown_clean_revision_without_success(harness):
    from test_source_pdf_reader import make_pdf
    from data_fetch.market_sources.pcsc_conference import PROVIDER
    harness[0][PDF]=make_pdf([b'PCSC 2912 a future clean presentation requiring semantic qualification'])
    result=acquire()
    assert not result.data['earnings_call']
    audits=[a for a in result.source_audit if a.get('provider')==PROVIDER]
    assert len(audits)==1 and audits[0]['record_count']==0
    assert audits[0]['status']!='success' and audits[0]['error_kind']=='unqualified_revision'
    assert audits[0]['http_request_count']==4 and not audits[0].get('pcsc_originals_verified')
