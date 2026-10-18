"""Future normal acquisition must find issuer bodies, with original evidence."""
from copy import deepcopy
from pathlib import Path
import gzip
import json
import time
import pytest

NOW = 1792113000.
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://cht.seec.com.tw/Content/Messagess/contents.aspx?SiteID=10&MmmID=655617024476060631'
PDF = 'https://cht.seec.com.tw/WebTools/FilesDownload.ashx?Siteid=10&MmmID=655617024476060631&fd=Messagess_NFiles&RD=2&Pname=%e6%b3%95%e8%aa%aa%e6%9c%83%e7%b0%a1%e5%a0%b1%e6%aa%94(%e4%b8%ad%e6%96%87)-%e4%b8%8a%e5%82%b3%e7%89%88_20260911081231.pdf&MSID=1'
F = Path(__file__).parent / 'fixtures/source_acquisition'


@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch import earnings_call_fetcher
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: {})
    bodies = {MASTER: gzip.decompress((F/'tcfhc5880_master_20261013.gz').read_bytes()),
              INDEX: gzip.decompress((F/'seec1503_index_20261016.gz').read_bytes()),
              PDF: gzip.decompress((F/'seec1503_pdf_20261016.gz').read_bytes())}
    calls = []
    if (Path(__file__).parents[1]/'backend/data_fetch/market_sources/seec_conference_transport.py').exists():
        from data_fetch.market_sources.seec_conference_transport import SeecConferenceHttp
        from data_fetch.market_sources import issuer_news_transport as native, gce_conference_transport as master_native
        monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
        for k in native.PROXY_ENV: monkeypatch.delenv(k, raising=False)
        def process(args, deadline, **options):
            assert args[-1] == MASTER
            raw = bodies[MASTER]; calls.append(MASTER)
            return {'body': raw, 'headers': b'HTTP/2 200\r\nContent-Type: text/csv\r\n\r\n',
                    'metadata': json.dumps({'http_code':200,'url_effective':MASTER,'num_redirects':0,
                        'size_download':len(raw),'content_type':'text/csv','method':'GET','proxy_used':0}).encode(),
                    'process_started':True}, 0, None
        for module in (native, master_native):
            monkeypatch.setattr(module, 'collect_capped_process', process)
            monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
            monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
        def download(self, url, diagnostic):
            import base64
            from hashlib import sha256
            calls.append(url); self.http_request_count += 1
            raw = bodies[url]
            diagnostic.update(http_request_sent=True, http_status=200)
            return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                    'http_status':200,'response_complete':True,'request_method':'GET',
                    'http_status_observed':True,'fetched_at_epoch':time.time()}
        monkeypatch.setattr(SeecConferenceHttp, '_download', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_public_source_acquires_body_not_date_only_old_link(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details = {}; value = fetch_free_earnings_call_context('1503.TW', diagnostics=details)
    assert value.get('documents'), 'Normal acquisition must replace metadata with the published body'
    doc = value['documents'][0]
    assert doc['url'] == PDF and doc['page_count'] == 10 and len(doc['pages']) == 10
    assert value['date'] == '2026-09-10' and value['transcript_available'] is False
    assert doc['coverage_status'] == 'partial' and not doc['full_content_coverage_verified']
    assert details['seec_originals_verified'] is True


def test_conflicting_company_blocks_before_network(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('1503.TW'), {'data':{
        'ticker':'1503.TW','company_name':'雙鴻','quote_type':'EQUITY'}})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert not harness[1]


def test_observed_cache_english_name_is_same_issuer(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('1503.TW'), {'data':{
        'ticker':'1503.TW', 'quote_type':'EQUITY', 'company_name':'士電 / Shihlin Electric & Engineering Corp.',
        'company_identity':{'stock_id':'1503', 'official_name':'士電', 'official_ubn':'11039306'}}})
    assert result.status == 'success' and result.value['documents'][0]['page_count'] == 10



@pytest.mark.parametrize('change', ['text','date','url','transcript','omissions','receipt','age','identity'])
def test_original_replay_rejects_tampering(harness, change):
    from data_fetch.market_sources import seec_conference as source
    v = source.fetch_seec_context('1503.TW')
    if change == 'text': v['documents'][0]['pages'][0]['text'] += 'fabricated'
    elif change == 'date': v['date'] = '2026-10-16'
    elif change == 'url': v['documents'][0]['url'] += '?new=1'
    elif change == 'transcript': v['transcript_available'] = True
    elif change == 'omissions': v['documents'][0]['known_native_text_omission_pages'] = []
    elif change == 'receipt': v.pop('seec_conference_receipt')
    elif change == 'age': v['seec_conference_receipt']['pdf']['retrieved_at'] = NOW - 86401
    else: v['ticker'] = '6577.TWO'
    assert source.is_marked(v) and not source.verify_context(v, '1503.TW')








def test_warm_replay_is_not_new_acquisition(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    p=EarningsCallProvider();request=FetchRequest.from_ticker('1503.TW')
    cold=p.fetch(request);calls=len(harness[1]);warm=p.fetch(request)
    assert cold.status=='success' and cold.audit['record_count']==1
    assert warm.audit['status']=='skipped_fresh_cache' and calls==3 and len(harness[1])==4 and harness[1][-1]==INDEX
    assert warm.value['fetched_at_epoch']==cold.value['fetched_at_epoch']==NOW




@pytest.mark.parametrize('tampered',[False,True])
def test_report_refresh_preserves_analysis_and_verifies_original(harness,tmp_path,monkeypatch,tampered):
    import asyncio
    from fastapi import HTTPException
    from data_fetch import StockDataService,ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import seec_conference as source
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db();storage=InMemoryStorage();filename,keys,old=saved_report(storage)
    old=json.loads(json.dumps(old,ensure_ascii=False).replace('6214.TW','1503.TW').replace('精誠','士電'))
    old['data']['quote_type']='EQUITY';original=json.dumps(old).encode()
    storage.save_report(keys.data_key,original,content_type='application/json')
    if tampered:
        acquire=source.fetch_seec_context
        def altered(*a,**kw):
            v=acquire(*a,**kw);v['documents'][0]['pages'][7]['text']+=' fabricated revenue';return v
        monkeypatch.setattr(source,'fetch_seec_context',altered)
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    def refresh():return asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='earnings_call',return_refreshed_data=True))
    if tampered:
        with pytest.raises(HTTPException) as exc:refresh()
        assert exc.value.status_code==502 and storage.get_report(keys.data_key).content==original
    else:
        assert refresh()['analysis_text_stale'] is True
        new=json.loads(storage.get_report(keys.data_key).content)
        assert new['data']['earnings_call']['documents'][0]['page_count']==10
        for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert new[k]==old[k]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'


def test_source_only_request_keeps_company_context_before_any_http(harness):
    import asyncio
    from data_fetch import StockDataService,ProviderRegistry,FetchRequest
    from data_fetch.enrichment_providers import EarningsCallProvider
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    result=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('1503.TW'),'earnings_call',context={'data':{
        'ticker':'1503.TW','company_name':'雙鴻','quote_type':'EQUITY'}}))
    assert not result.data.get('earnings_call') and not harness[1]

@pytest.mark.parametrize('tampered',[False,True])
def test_actual_agent_prompt_keeps_verified_body_and_never_internal_receipts(harness,tampered):
    from data_fetch.market_sources.seec_conference import fetch_seec_context
    from agent_runtime.prompting import data_for_agent_prompt
    value=fetch_seec_context('1503.TW')
    if tampered:value['documents'][0]['pages'][3]['text'] += ' fabricated profit'
    data={'ticker':'1503.TW','company_name':'士電','earnings_call':value}
    before=deepcopy(data)
    for role in (3,5,12):
        result=data_for_agent_prompt(role,data)
        assert bool(result.get('conference_presentation')) is (not tampered)
        assert 'seec_conference_receipt' not in json.dumps(result,ensure_ascii=False)
    assert data==before


def test_failed_warm_handoff_is_failure_not_empty_cache(harness,monkeypatch):
 from data_fetch.market_sources import seec_conference as source
 from data_fetch.enrichment_providers import EarningsCallProvider
 from data_fetch.types import FetchRequest
 from provider_acquisition import observation_kind
 p=EarningsCallProvider();req=FetchRequest.from_ticker('1503.TW')
 cold=p.fetch(req,{'data':{'ticker':'1503.TW','quote_type':'EQUITY','company_name':'士電'}});assert cold.status=='success'
 old_count=len(harness[1]);original_deepcopy=source.deepcopy;original_monotonic=time.monotonic
 state={'late':False}
 monkeypatch.setattr(time,'monotonic',lambda:original_monotonic()+(21 if state['late'] else 0))
 def slow_components(value,*a,**kw):
  out=original_deepcopy(value,*a,**kw)
  if isinstance(value,list) and value and all(isinstance(x,dict) and 'url' in x for x in value):state['late']=True
  return out
 monkeypatch.setattr(source,'deepcopy',slow_components)
 failed=p.fetch(req,{'data':{'ticker':'1503.TW','quote_type':'EQUITY','company_name':'士電'}})
 assert state['late'] and failed.status=='error' and not failed.value
 assert len(harness[1])==old_count+1 and failed.audit['http_request_count']==1
 assert failed.audit['record_count']==0 and not failed.audit['seec_originals_verified']
 row={**failed.audit,'details':dict(failed.audit)}
 assert observation_kind(row)=='failed_count',failed.audit
 assert 'coverage_status' not in failed.audit

def test_dynamic_index_binds_year_not_position_or_filename_date(harness, monkeypatch):
    from data_fetch.market_sources.seec_conference import select_presentation
    from datetime import datetime
    from zoneinfo import ZoneInfo
    raw = harness[0][INDEX]
    value = select_presentation(raw, NOW)
    assert value['event_date'] == '2026-09-10' and 'material_file_date' not in value
    assert value['pdf_url'] == PDF
    # A new edition is discovered from the actual index, not pinned to its digest.
    new = raw.decode().replace('2026年09月10日', '2027年09月09日').replace('2026年法人說明會', '2027年法人說明會').replace('2026年法說會簡報檔', '2027年法說會簡報檔').replace('20260911081231.pdf', '20270910090000.pdf')
    epoch = datetime(2027, 10, 1, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monkeypatch.setattr(time, 'time', lambda: epoch)
    selected = select_presentation(new.encode(), epoch, as_of_epoch=epoch)
    assert selected['event_date'] == '2027-09-09'
    assert selected['pdf_url'] == PDF.replace('20260911081231', '20270910090000')


@pytest.mark.parametrize('edit', ['no_attachment', 'duplicate_attachment', 'duplicate_event', 'wrong_year', 'bad_host', 'truncated', 'wrong_title'])
def test_latest_unqualified_event_never_silently_uses_old_file(harness, edit):
    from bs4 import BeautifulSoup
    from data_fetch.market_sources.seec_conference import select_presentation
    soup = BeautifulSoup(harness[0][INDEX], 'html.parser')
    a = next(a for a in soup.find_all('a', href=True) if a.get_text(' ',strip=True) == '2026年法說會簡報檔(PDF)(檔案下載)')
    if edit == 'no_attachment': a.decompose()
    elif edit == 'duplicate_attachment': a.insert_after(deepcopy(a))
    elif edit == 'duplicate_event': soup.table.find_all('tr')[1].insert_after(deepcopy(soup.table.find_all('tr')[1]))
    elif edit == 'wrong_year': a.string = '2020年法說會簡報檔(PDF)(檔案下載)'
    elif edit == 'bad_host': a['href'] = 'https://unrelated.example/' + a['href']
    elif edit == 'wrong_title': soup.title.string = 'Other company'
    raw = str(soup).encode()
    if edit == 'truncated': raw = raw.replace(b'</html>', b'')
    with pytest.raises(ValueError): select_presentation(raw, NOW)


def test_native_cover_cannot_be_relabelled_as_other_year(harness):
    from data_fetch.market_sources import seec_conference as source
    selected = source.select_presentation(harness[0][INDEX], NOW)
    selected['event_date'] = '2025-09-10'
    with pytest.raises(ValueError, match='year unverified'):
        source.native_presentation(harness[0][PDF], selected, time.monotonic()+10)


def test_role_projection_preserves_real_omissions_and_half_year_scope(harness):
    from data_fetch.market_sources.seec_conference import fetch_seec_context
    from conference_presentation_prompt import presentation_prompt_context
    from prompt_evidence import prompt_evidence_copy
    value = fetch_seec_context('1503.TW'); before = deepcopy(value)
    raw = value['documents'][0]
    assert raw['known_native_text_omission_pages'] == [8, 9]
    assert raw['missing_text_pages'] == [10] and raw['garbled_pages'] == [2, 3]
    assert raw['native_text_coverage'] == 'partial' and not raw['text_extraction_complete']
    for role in (3, 5, 12):
        d = presentation_prompt_context(value, role)['documents'][0]
        assert [p['page_number'] for p in d['pages']] == [1, 6, 7]
        assert all(not p['content_truncated'] for p in d['pages'])
        assert d['known_native_text_omission_pages'] == [8, 9]
        assert '新台幣佰萬' in d['financial_scope_caution'] and 'EPS單位元' in d['financial_scope_caution']
        assert '前一年上半年' in d['financial_scope_caution'] and '無主動更新義務' in d['financial_scope_caution']
    assert value == before and 'seec_conference_receipt' not in prompt_evidence_copy(value)

@pytest.mark.parametrize('edit', ['missing_row', 'wrong_period', 'wrong_unit'])
def test_changed_financial_layout_is_not_projected_as_qualified_table(harness, edit):
    from data_fetch.market_sources import seec_conference as source
    d = source.fetch_seec_context('1503.TW')['documents'][0]
    if edit == 'missing_row': d['pages'][6]['text'] = d['pages'][6]['text'].replace('營業收入', 'missing')
    elif edit == 'wrong_period': d['pages'][6]['text'] = d['pages'][6]['text'].replace('114年H1', '113年H1')
    else: d['pages'][6]['text'] = d['pages'][6]['text'].replace('新台幣佰萬', '新台幣千元')
    assert [p['page_number'] for p in source.role_pages(d)] == [1, 6]


@pytest.mark.parametrize('both_sources', [False, True])
def test_source_rename_never_bypasses_original_verification(harness, both_sources):
    from data_fetch.market_sources.seec_conference import fetch_seec_context
    from agent_runtime.prompting import data_for_agent_prompt
    value = fetch_seec_context('1503.TW')
    value['documents'][0]['source'] = 'issuer_official'
    value['documents'][0]['pages'][6]['text'] += '\nUnverified fabricated profit'
    if both_sources: value['source'] = 'issuer_official'
    output = data_for_agent_prompt(3, {'ticker': '1503.TW', 'earnings_call': value})
    assert not output.get('conference_presentation')
    assert 'Unverified fabricated profit' not in json.dumps(output)


def test_final_equality_cannot_finish_after_verification_deadline(harness, monkeypatch):
    from data_fetch.market_sources.seec_conference import fetch_seec_context, verify_context
    from search_provider_runtime import SourceResponseError
    value = fetch_seec_context('1503.TW')
    clock = time.monotonic; late = {'value': False}
    monkeypatch.setattr(time, 'monotonic', lambda: clock() + (20 if late['value'] else 0))
    class SlowEqual(dict):
        def __eq__(self, other):
            late['value'] = True
            return dict.__eq__(self, other)
    with pytest.raises(SourceResponseError) as exc:
        verify_context(SlowEqual(value), '1503.TW', deadline=clock()+2, max_age=1800)
    assert exc.value.error_kind == 'timeout'
