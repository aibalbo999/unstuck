"""Recover the actual Delta original without accepting guessed transcript text."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import gzip,time
import pytest

NOW=datetime(2026,10,13,15,45,tzinfo=timezone.utc).timestamp()
F=Path(__file__).parent/'fixtures/source_acquisition'
MASTER='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX='https://www.deltaww.com/en-US/investors/analyst-meeting'
PDF='https://filecenter.deltaww.com/IR/download/calendar/2Q26_Transcript.pdf'

@pytest.fixture
def harness(monkeypatch):
    from data_fetch import earnings_call_fetcher
    from cache_backends import InMemoryCache
    import cache_store
    cache_store.set_cache_backend(InMemoryCache());monkeypatch.setattr(time,'time',lambda:NOW)
    monkeypatch.setattr(earnings_call_fetcher,'_fetch_official_index_context',lambda *a,**kw:{})
    bodies={u:gzip.decompress((F/('delta2308_'+role+'_20261013.gz')).read_bytes())for u,role in ((MASTER,'master'),(INDEX,'index'),(PDF,'transcript'))};calls=[]
    if (Path(__file__).parents[1]/'backend/data_fetch/market_sources/delta_conference_transport.py').exists():
        from data_fetch.market_sources.delta_conference_transport import ConferenceHttp
        def download(self,url,diagnostic):
            from hashlib import sha256
            import base64
            calls.append(url);self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200);raw=bodies[url]
            return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),'http_status':200,'response_complete':True,'request_method':'GET','http_status_observed':True,'fetched_at_epoch':time.time()}
        monkeypatch.setattr(ConferenceHttp,'_download',download)
        from data_fetch.market_sources import conference_issuer_master as master_adapter
        from data_fetch.market_sources import official_issuer_master as shared

        def master_download(self, url, diagnostic):
            value = download(self, url, diagnostic)
            import base64
            raw = base64.b64decode(value['body_b64'])
            meta = {'http_status':200, 'effective_url':url, 'num_redirects':0,
                    'size_download':len(raw), 'content_type':'text/csv', 'content_length':len(raw),
                    'method':'GET', 'proxy_used':0, 'cache_control':''}
            value['response_metadata'] = shared.master_metadata(meta, raw, {})
            return value
        monkeypatch.setattr(master_adapter._ConferenceMasterHttp, 'download_original', master_download)
    yield bodies,calls
    cache_store.reset_cache_store_for_tests()

def test_actual_original_recovers_embedded_ligatures_and_keeps_proof():
    from source_pdf_reader import extract_pdf_pages
    raw=gzip.decompress((F/'delta2308_transcript_20261013.gz').read_bytes());native=extract_pdf_pages(raw)
    assert native['coverage_status']=='complete','known embedded ft/tf/ti/tt glyphs must decode from qualified original'
    assert native['page_count']==13 and not native['garbled_pages']
    assert 'Meeting' in native['pages'][0]['text'] and 'afternoon' in native['pages'][0]['text']
    assert 'submitted' in native['pages'][0]['text'] and 'attending' in native['pages'][0]['text']
    assert len(native['native_font_mapping_evidence'])==2

def test_public_call_recovers_translated_issuer_transcript(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    diagnostics={};value=fetch_free_earnings_call_context('2308.TW',diagnostics=diagnostics)
    assert value.get('documents'),'published official transcript must replace metadata-only fallback'
    doc=value['documents'][0]
    assert value['date']=='2026-07-30'and doc['page_count']==13
    assert doc['document_kind']=='transcript'and doc['language']=='en'
    assert doc['translated_from_language']=='zh-TW'and doc['translation_accuracy_verified']is False
    assert doc['native_font_mapping_evidence']and doc['full_content_coverage_verified']is False
    assert diagnostics['delta_originals_verified']is True

def test_unknown_document_is_not_guessed_even_when_font_bytes_match():
    from source_pdf_reader import extract_pdf_pages
    raw=gzip.decompress((F/'delta2308_transcript_20261013.gz').read_bytes())+b'\n% different document identity\n'
    native=extract_pdf_pages(raw)
    assert native['coverage_status']=='partial'and native['garbled_pages']==list(range(1,14))
    assert 'native_font_mapping_evidence'not in native

@pytest.mark.parametrize('change',['font','cmap','cid_map','encoding'])
def test_unqualified_embedded_font_never_partially_mutates_known_document(change):
    import io
    from pypdf import PdfReader
    from pypdf.generic import NameObject,DecodedStreamObject
    from source_pdf_delta_ligatures import qualify_embedded_ligatures,DOCUMENT_SHA256
    doc=PdfReader(io.BytesIO(gzip.decompress((F/'delta2308_transcript_20261013.gz').read_bytes())),strict=True)
    font=doc.pages[0]['/Resources']['/Font']['/C2_1'];before=font['/ToUnicode'].get_data()
    if change=='font':
        stream=DecodedStreamObject();stream.set_data(b'not the qualified font');font['/DescendantFonts'][0]['/FontDescriptor'][NameObject('/FontFile2')]=stream
    elif change=='cmap':
        stream=DecodedStreamObject();stream.set_data(before+b'\n');font[NameObject('/ToUnicode')]=stream
    elif change=='cid_map':font['/DescendantFonts'][0].get_object()[NameObject('/CIDToGIDMap')]=NameObject('/Other')
    else:font[NameObject('/Encoding')]=NameObject('/Identity-V')
    expected=font['/ToUnicode'].get_data()
    assert qualify_embedded_ligatures(doc,DOCUMENT_SHA256)==[]
    assert font['/ToUnicode'].get_data()==expected
    assert b'<019F> <FFFD>'in doc.pages[0]['/Resources']['/Font']['/C2_0']['/ToUnicode'].get_data()

@pytest.mark.parametrize('change',['text','date','translation','kind','hash','missing','future','expired','http','extra','font_map'])
def test_changed_saved_packet_fails_original_replay(harness,change):
    from data_fetch.market_sources import delta_conference as s
    value=s.fetch_delta_context('2308.TW');doc=value['documents'][0];proof=value['delta_transcript_receipt']
    if change=='text':doc['pages'][0]['text']+=' invented'
    elif change=='date':value['date']='2026-08-30'
    elif change=='translation':doc['translation_accuracy_verified']=True
    elif change=='kind':doc['document_kind']='presentation'
    elif change=='hash':proof['transcript']['raw_response_sha256']='0'*64
    elif change=='missing':value.pop('delta_transcript_receipt')
    elif change=='future':proof['identity']['retrieved_at']=NOW+1
    elif change=='expired':proof['index']['retrieved_at']=NOW-86400
    elif change=='http':proof['transcript']['http_status']=None
    elif change=='font_map':doc['native_font_mapping_evidence'][0]['mappings'][0]['decoded_unicode_hex']='0030'
    else:value['extra']='unverified'
    assert s.is_marked(value)and not s.verify_context(value,'2308.TW')

@pytest.mark.parametrize('context',[{'ticker':'2308.TW','quote_type':'ETF'},
    {'ticker':'5880.TW','quote_type':'EQUITY'},{'ticker':'2308.TW','quote_type':'EQUITY','company_identity':False},
    {'ticker':'2308.TW','quote_type':'EQUITY','company_identity':{'official_ubn':'12345678'}}])
def test_conflicting_security_rejected_before_provider(harness,context):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('2308.TW'),{'data':context})
    assert result.status=='unavailable'and result.audit['event_kind']=='local_block'and not harness[1]

def test_cold_then_warm_retains_epoch_and_counts_one_acquisition(harness):
    import json
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from provider_acquisition import project_acquisition_events
    p=EarningsCallProvider();request=FetchRequest.from_ticker('2308.TW');cold=p.fetch(request)
    assert cold.status=='success'and cold.audit['http_request_count']==3 and harness[1]==[MASTER,INDEX,PDF]
    harness[1].clear();warm=p.fetch(request)
    assert warm.status=='skipped_fresh_cache'and not harness[1]
    assert cold.value['fetched_at_epoch']==warm.value['fetched_at_epoch']==NOW
    events=[]
    for result in (cold,warm):
        a=result.audit;events.append({'source':'earnings_call','provider':a['provider'],'status':a['status'],'record_count':a['record_count'],'message':a['message'],'created_at':NOW,'details_json':json.dumps(a)})
    row=project_acquisition_events(events,window='last_24h',now=NOW)['sources'][0]
    assert row['fetched_count']==row['fetch_attempts']==row['fresh_cache_count']==1

def test_role_prompt_retains_translation_limits_and_200_word_bound(harness):
    from data_fetch.market_sources.delta_conference import fetch_delta_context
    from conference_presentation_prompt import presentation_prompt_context,without_presentation_documents
    from prompt_evidence import prompt_evidence_copy
    v=fetch_delta_context('2308.TW');before=deepcopy(v)
    for agent in (3,5,12):
        out=presentation_prompt_context(v,agent);doc=out['documents'][0]
        assert sum(len(p['text'].split())for p in doc['pages'])<=200
        assert doc['translation_accuracy_verified']is False and doc['translated_from_language']=='zh-TW'
        assert '中文原音'in out['evidence_policy']and doc['omitted_page_count']>0
    assert 'documents'not in without_presentation_documents(v)
    assert 'delta_transcript_receipt'not in prompt_evidence_copy(v)and v==before

@pytest.mark.parametrize('kind',['timeout','lease_lost','single_flight_busy','guard_storage_unavailable'])
def test_terminal_failure_does_not_trigger_more_requests(harness,monkeypatch,kind):
    from data_fetch.market_sources import delta_conference as s
    from data_fetch import earnings_call_fetcher as f
    from search_provider_runtime import SourceResponseError
    def fail(*a,**kw):raise SourceResponseError(kind)
    monkeypatch.setattr(s,'fetch_delta_context',fail)
    monkeypatch.setattr(f,'_fetch_official_index_context',lambda *a,**kw:pytest.fail('extra request after terminal error'))
    with pytest.raises(SourceResponseError)as exc:f.fetch_free_earnings_call_context('2308.TW')
    assert exc.value.error_kind==kind

@pytest.mark.parametrize('change',['master','attachment','date','owner','transcript_absent'])
def test_public_originals_must_bind_correct_issuer_and_period(harness,change):
    from data_fetch.market_sources import delta_conference as s
    from search_provider_runtime import SourceResponseError
    bodies,calls=harness
    if change=='master':bodies[MASTER]=bodies[MASTER].replace(b'34051920',b'12345678')
    elif change=='attachment':bodies[INDEX]=bodies[INDEX].replace(b'2Q26_Transcript.pdf',b'1Q26_Transcript.pdf')
    elif change=='date':bodies[INDEX]=bodies[INDEX].replace(b'07/30/2026',b'07/31/2026')
    elif change=='owner':bodies[INDEX]=bodies[INDEX].replace(b'Stock ticker:2308',b'Stock ticker:2309')
    else:bodies[INDEX]=bodies[INDEX].replace(b'>Transcript</a>',b'>Other</a>')
    with pytest.raises(SourceResponseError):s.fetch_delta_context('2308.TW')

def test_final_original_ttl_rechecked_after_pdf_extraction(harness,monkeypatch):
    from data_fetch.market_sources import delta_conference as s
    value=s.fetch_delta_context('2308.TW');old=s.native_transcript
    def advance(*a,**kw):
        result=old(*a,**kw);monkeypatch.setattr(time,'time',lambda:NOW+1800);return result
    monkeypatch.setattr(s,'native_transcript',advance)
    assert not s.verify_context(value,'2308.TW',max_age=1800)


def test_source_only_transcript_refresh_preserves_report_and_core_observations(harness, tmp_path):
    import asyncio
    import json
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db, events
    init_db()
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    def replace(value):
        if isinstance(value, str): return value.replace('6214.TW', '2308.TW').replace('精誠', '台達電')
        if isinstance(value, dict): return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list): return [replace(v) for v in value]
        return value
    old = replace(old)
    old['data']['quote_type'] = 'EQUITY'
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    response = asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                            refresh_service=service, source='earnings_call', return_refreshed_data=True))
    new = json.loads(storage.get_report(keys.data_key).content)
    assert new['data']['earnings_call']['documents'][0]['document_kind'] == 'transcript'
    for key in ['current_price', 'revenue_history', 'years', 'peer_discovery_results']:
        assert new['data'][key] == old['data'][key]
    assert next(a for a in new['source_audit'] if a['source'] == 'market_data') == old['source_audit'][0]
    for key in ['analysis_evidence', 'report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert new[key] == old[key]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert response['analysis_text_stale'] is True
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call' and observed[0]['status'] == 'success'


def test_newer_meeting_without_attachments_prevents_older_transcript(harness):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.delta_conference import select_transcript
    soup = BeautifulSoup(harness[0][INDEX].decode(), 'html.parser')
    card = next(a.parent.parent for a in soup.select('a[href]')
                if a.get_text(' ', strip=True) == 'Document' and '07/30/2026' in a.parent.parent.get_text())
    newer = BeautifulSoup(str(card).replace('07/30/2026', '10/12/2026')
                          .replace('2Q Analyst Meeting', '3Q Analyst Meeting'), 'html.parser')
    for anchor in newer.select('a'): anchor.decompose()
    soup.body.append(newer)
    assert select_transcript(str(soup).encode()) is None


@pytest.mark.parametrize('key,bad', [('source', {}), ('source', []),
                                   ('projection_policy', {}), ('projection_policy', [])])
def test_malformed_unrelated_document_keeps_existing_prompt_behavior(key, bad):
    from conference_presentation_prompt import without_presentation_documents, presentation_prompt_context
    from conference_transcript_prompt import marked
    document = {'document_kind': 'transcript', 'source': 'unrelated',
                'projection_policy': 'unrelated', 'pages': [{'page_number': 1, 'text': 'source text'}]}
    document[key] = bad
    context = {'documents': [document]}
    assert marked(document) is False
    assert without_presentation_documents(context) == context
    assert presentation_prompt_context(context, 3) == {}


def test_real_mops_fallback_reports_actual_source_and_preserves_delta_failure(monkeypatch):
    from data_fetch.market_sources import delta_conference
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from search_provider_runtime import SourceResponseError
    import official_financials
    monkeypatch.setattr(time, 'time', lambda: NOW)
    def missing(*args, **kwargs): raise SourceResponseError('transcript_not_published')
    def mops(ticker, **kwargs):
        kwargs['diagnostics'].update(cache_hit=False, http_request_sent=True,
                                     http_request_count=1, fetched_at_epoch=NOW)
        return [{'ticker': ticker, 'date': '2026-07-30', 'title': 'Official event metadata',
                 'summary': 'published event only', 'materials': [], 'source_url': 'https://mops.twse.com.tw/'}]
    monkeypatch.setattr(delta_conference, 'fetch_delta_context', missing)
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', mops)
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('2308.TW'))
    assert result.value['transcript_available'] is False
    assert result.audit['provider'] == result.value['source'] == 'MOPS investor conference'
    assert result.audit['component_statuses']['Delta_transcript']['error_kind'] == 'transcript_not_published'
