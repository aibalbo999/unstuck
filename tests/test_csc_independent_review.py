"""Independent public CSC boundary checks; native I/O is fixture-only."""
from copy import deepcopy
from hashlib import sha256
import time
import pytest
from test_csc_conference import harness, valid_data, NOW, MASTER_URL, INDEX_URL, PDF_URL, raw_key


@pytest.mark.parametrize('boundary', ['deadline', 'ttl'])
def test_final_diagnostic_handoff_must_not_deliver_expired_original(harness, monkeypatch, boundary):
    from data_fetch.market_sources import csc_conference as source
    from search_provider_runtime import SourceResponseError
    wall=[NOW]; mono=[time.monotonic()]
    monkeypatch.setattr(time,'time',lambda:wall[0])
    monkeypatch.setattr(time,'monotonic',lambda:mono[0])
    class DelayedHandoff(dict):
        def update(self,*args,**kwargs):
            super().update(*args,**kwargs)
            if self.get('csc_originals_verified') is True:
                if boundary=='deadline':mono[0]+=26
                else:wall[0]+=1800
    diagnostic=DelayedHandoff()
    with pytest.raises(SourceResponseError) as failure:
        source.fetch_csc_context('2002.TW',diagnostics=diagnostic)
    assert diagnostic['csc_originals_verified'] is False
    assert diagnostic['status']=='error' and diagnostic['http_request_count']==3
    assert not {'coverage_status','cache_hit','stale','fetched_at_epoch'} & diagnostic.keys()
    assert not {'coverage_status','cache_hit','stale','fetched_at_epoch'} & failure.value.diagnostic.keys()
    assert failure.value.diagnostic['csc_originals_verified'] is False


@pytest.mark.parametrize('cached',[False,True])
def test_public_reader_timeout_stays_error_with_actual_native_count(harness,monkeypatch,cached):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch import earnings_call_fetcher as fetcher
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from source_pdf_reader import SourcePdfError
    if cached:source.fetch_csc_context('2002.TW');harness[1].clear()
    def timeout(*a,**kw):raise SourcePdfError('timeout')
    monkeypatch.setattr(source,'extract_csc_presentation_pages',timeout)
    monkeypatch.setattr(fetcher,'_fetch_official_index_context',lambda *a,**kw:pytest.fail('fatal timeout cannot start fallback'))
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2002.TW'),{'data':valid_data()})
    assert not result.value and result.audit['status']=='error'
    assert result.audit['record_count']==0 and result.audit['csc_originals_verified'] is False
    assert result.audit['http_request_count']==(0 if cached else 3)
    assert result.audit['http_request_sent'] is (not cached)
    assert result.audit.get('coverage_status')!='native_presentation_text_complete'


@pytest.mark.parametrize('pdf_fresh',[False,True])
def test_public_mixed_cache_freshness_follows_body_not_metadata(harness,monkeypatch,pdf_fresh):
    from data_fetch.market_sources import csc_conference as source
    from data_fetch.market_sources.csc_conference_transport import ConferenceHttp
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    import cache_store
    source.fetch_csc_context('2002.TW');harness[1].clear()
    monkeypatch.setattr(time,'time',lambda:NOW+1)
    stale_urls=[PDF_URL] if pdf_fresh else [MASTER_URL,INDEX_URL]
    for url in stale_urls:
        key=raw_key(url)
        row=cache_store.get_cache_json(key);row['fresh_until_epoch']=NOW+0.5
        cache_store.set_cache_json(key,row,ttl_seconds=1800)
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2002.TW'),{'data':valid_data()})
    assert result.value['documents'][0]['page_count']==35
    assert result.audit['status']==('success' if pdf_fresh else 'skipped_fresh_cache')
    assert result.audit['cache_hit'] is (not pdf_fresh)
    assert result.audit['http_request_count']==len(stale_urls)
    assert result.value['fetched_at_epoch']==(NOW+1 if pdf_fresh else NOW)
    assert harness[1]==stale_urls


@pytest.mark.parametrize('request_ticker,data_ticker',[('2330.TW','2002.TW'),('2002.TW','2002.TWO')])
def test_cross_requested_and_resolved_subject_never_reaches_source(monkeypatch,request_ticker,data_ticker):
    from data_fetch import enrichment_providers as providers
    from data_fetch.types import FetchRequest
    data=valid_data();data['ticker']=data_ticker
    monkeypatch.setattr(providers,'fetch_free_earnings_call_context',lambda *a,**kw:pytest.fail('cross subject HTTP'))
    result=providers.EarningsCallProvider().fetch(FetchRequest.from_ticker(request_ticker),{'data':data})
    assert not result.value and result.audit['error_kind']=='context_unverified'
    assert result.audit['http_request_count']==0


def test_real_pages_roles_preserve_cautions_and_strip_private_receipts(harness):
    from data_fetch.market_sources import csc_conference as source
    from conference_presentation_prompt import presentation_prompt_context
    from prompt_evidence import prompt_evidence_copy
    value=source.fetch_csc_context('2002.TW');before=deepcopy(value)
    for role in (3,5,12):
        doc=presentation_prompt_context(value,role)['documents'][0]
        assert doc['content_periods']==value['documents'][0]['content_periods']
        assert doc['period_scope_caution'] and doc['unaudited_financial_caution']
        assert doc['coverage_status']=='partial' and not doc['q_and_a_transcript_available']
        assert sum(len(p['text'].split()) for p in doc['pages'])<=200
    public=prompt_evidence_copy(value)
    assert 'csc_conference_receipt' not in public
    assert 'csc_glyph_evidence' not in public['documents'][0]
    assert value==before
