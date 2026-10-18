"""A verified issuer index can recover a temporary MOPS failure."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RAW = (Path(__file__).parent / 'fixtures/source_acquisition/systex_20261010_conference_index.json').read_bytes()
HOME = b'<html><script>window.__X_UNIQUE_ID__ = "anonymous_server_issued_parameter_1234567890";</script></html>'


@pytest.fixture
def upstream(monkeypatch):
    import official_financials
    import official_financials_webpro_conference as webpro
    import bounded_curl_process
    import search_provider_runtime as runtime
    import cache_store
    import company_conference_transport
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from search_provider_runtime import SourceResponseError
    state, observations, requests = {}, [], []
    for module in (runtime, cache_store):
        monkeypatch.setattr(module, 'get_cache_json', lambda key: state.get(key))
        monkeypatch.setattr(module, 'set_cache_json', lambda key, value, ttl_seconds: state.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda rows: observations.extend(rows))
    monkeypatch.setattr(company_conference_transport, '_VERSION', None)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    def fail_mops(*a, **k):
        raise SourceResponseError('server_error', status_code=502)
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events', fail_mops)
    def old_fallback(ticker, diagnostics):
        diagnostics.update(actual_provider='TWSE WebPro conference metadata', coverage_status='partial')
        return {'ticker': '6214', 'date': '2026-09-17', 'summary': '', 'materials': [],
                'source': 'TWSE WebPro conference metadata'}
    monkeypatch.setattr(webpro, 'fetch_webpro_conference_context', old_fallback)
    from data_fetch import earnings_call_fetcher as fetcher
    monkeypatch.setattr(fetcher, '_fetch_twse_iih_notice_fallback', lambda *a, **k: {})
    monkeypatch.setattr(fetcher, '_fetch_irengage_fallback', lambda ticker, context, *a, **k: context)
    def native(args, deadline, **kwargs):
        if '--version' in args:
            return {'body': b'curl 8.7.1 test', 'metadata': b'', 'headers': b'', 'process_started': True}, 0, None
        url = args[-1]; requests.append(url)
        path = urlsplit(url).path
        raw = HOME if path == '/systex/ch/index' else RAW
        kind = 'text/html' if raw == HOME else 'application/json'
        return {'body': raw, 'headers': ('HTTP/2 200\r\nContent-Type: '+kind+'\r\n\r\n').encode(),
                'metadata': json.dumps({'http_code': 200, 'url_effective': url, 'num_redirects': 0}).encode(),
                'process_started': True}, 0, None
    monkeypatch.setattr(bounded_curl_process, 'collect_capped_process', native)
    monkeypatch.setattr(company_conference_transport, 'collect_capped_process', native)
    import systex_conference_transport
    monkeypatch.setattr(systex_conference_transport, 'collect_capped_process', native)
    return state, observations, requests


def test_public_earnings_provider_recovers_issuer_event_details_after_mops_502(upstream):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    state, observations, requests = upstream
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('6214.TW'))
    assert result.provider == 'SYSTEX official investor conference index'
    assert result.value['date'] == '2026-09-17'
    assert '元大' in result.value['summary'] and result.value['materials']
    assert result.value['transcript_available'] is False
    assert result.audit['component_statuses']['MOPS']['http_status'] == 502
    assert len(requests) == 2
    assert 'anonymous_server_issued_parameter' not in json.dumps(result.value)
    assert observations and all(a['source'] == 'earnings_call' for a in observations)


def test_complete_original_selects_latest_past_year_and_same_event_materials():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from systex_conference_index import select_event
    assert hashlib.sha256(RAW).hexdigest() == 'c7017779dc0da199885342134ce5b3ca0e66a52843ab04aa86367c793f154721'
    event = select_event(RAW, now=datetime(2026,10,10,tzinfo=ZoneInfo('Asia/Taipei')))
    assert event['date'] == '2026-09-17' and event['time'] == '14:00'
    assert event['presentation_url'].endswith('/1550066653948022784.pdf')
    assert event['video_url'] == 'https://youtu.be/EKeD7lsU5Y0'


def test_future_event_does_not_displace_latest_eligible_event():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from systex_conference_index import select_event
    changed = RAW.replace('2026年9月17日'.encode(), '2026年12月17日'.encode())
    event = select_event(changed, now=datetime(2026,10,10,tzinfo=ZoneInfo('Asia/Taipei')))
    assert event['date'] == '2026-05-13'
    assert event['presentation_url'].endswith('/1512002453770342400.pdf')


@pytest.mark.parametrize('change', ['foreign_pdf', 'pdf_query', 'year_conflict', 'malformed_panel'])
def test_malformed_current_index_is_not_accepted_as_source_data(change):
    from systex_conference_index import select_event
    value = json.loads(RAW)
    row = value['viewModelList'][0]['tabViewModels'][0]['dataViewModels'][0]
    if change == 'foreign_pdf':
        previous = row['detailContent']
        row['detailContent'] = previous.replace('/userfiles/systexch/files/1550066653948022784.pdf', 'https://evil.example/fake.pdf')
        assert previous != row['detailContent']
    elif change == 'pdf_query':
        row['detailContent'] = row['detailContent'].replace('1550066653948022784.pdf', '1550066653948022784.pdf?redirect=x')
    elif change == 'year_conflict':
        row['detailContent'] = row['detailContent'].replace('2026年9月17日', '2025年9月17日')
    else:
        value['viewModelList'][0]['artWebSiteViewModel'] = 'not a year object'
    with pytest.raises(ValueError):
        select_event(json.dumps(value,ensure_ascii=False).encode())


def test_warm_source_preserves_original_epoch_and_no_new_http(upstream):
    from systex_conference_index import fetch_systex_conference_context
    first_details, warm_details = {}, {}
    first = fetch_systex_conference_context('6214.TW', diagnostics=first_details)
    warm = fetch_systex_conference_context('6214.TW', diagnostics=warm_details)
    assert first == warm and len(upstream[2]) == 2
    assert warm_details['fetched_at_epoch'] == first_details['fetched_at_epoch']
    assert warm_details['cache_hit'] is True and warm_details['source_http_request_count'] == 0
    assert warm_details['http_request_sent'] is False


@pytest.mark.parametrize('field', ['materials', 'source_url', 'receipt_url', 'receipt_missing'])
def test_altered_warm_context_or_receipt_is_rejected_without_http(upstream, field):
    from systex_conference_index import fetch_systex_conference_context
    from search_provider_runtime import SourceResponseError
    fetch_systex_conference_context('6214.TW')
    saved = next(v['value'] for v in upstream[0].values() if isinstance(v,dict) and isinstance(v.get('value'),dict) and 'context' in v['value'])
    if field == 'materials':
        saved['context']['materials'][0]['url'] = 'https://evil.example/fake.pdf'
    elif field == 'source_url':
        saved['context']['source_url'] = 'https://evil.example/index'
    elif field == 'receipt_url':
        saved['diagnostic']['raw_http_receipt']['source_url'] = 'https://evil.example/index'
    else:
        Path(saved['diagnostic']['raw_http_receipt']['raw_response_path']).unlink()
    with pytest.raises(SourceResponseError, match='來源取得失敗'):
        fetch_systex_conference_context('6214.TW')
    assert len(upstream[2]) == 2


def test_unsupported_issuer_has_no_source_work(upstream):
    from systex_conference_index import fetch_systex_conference_context
    assert fetch_systex_conference_context('6214.TWO') == {}
    assert fetch_systex_conference_context('2330.TW') == {}
    assert not upstream[2] and not upstream[1]


def test_healthy_mops_does_not_call_new_backup(upstream, monkeypatch):
    import official_financials
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    monkeypatch.setattr(official_financials, 'fetch_mops_investor_conference_events',
        lambda *a, **k: [{'ticker':'6214','date':'2026-09-17','summary':'issuer event description',
                         'materials':[{'url':'https://mopsov.twse.com.tw/nas/STR/621420260917M001.pdf'}]}])
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('6214.TW'))
    assert result.provider == 'MOPS investor conference' and not upstream[2]


def test_security_refusal_with_public_parameter_is_not_followed():
    from systex_conference_index import parse_nonce
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        parse_nonce(HOME+b'FOR SECURITY REASONS')


@pytest.mark.parametrize('change',[{'status':'unavailable'},{'evidence_kind':'selected_fields_only'},{'raw_response_bytes':1},{'raw_response_bytes':True},{'raw_response_bytes':512001}])
def test_warm_receipt_metadata_must_describe_complete_archive(upstream,change):
    from systex_conference_index import fetch_systex_conference_context
    from search_provider_runtime import SourceResponseError
    fetch_systex_conference_context('6214.TW')
    saved=next(v['value'] for v in upstream[0].values() if isinstance(v,dict) and isinstance(v.get('value'),dict) and 'context' in v['value'])
    saved['diagnostic']['raw_http_receipt'].update(change)
    with pytest.raises(SourceResponseError):fetch_systex_conference_context('6214.TW')
    assert len(upstream[2])==2


def test_huge_warm_epoch_remains_typed_error_and_webpro_fallback(upstream,monkeypatch):
    from systex_conference_index import fetch_systex_conference_context
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    fetch_systex_conference_context('6214.TW')
    saved=next(v['value'] for v in upstream[0].values() if isinstance(v,dict) and isinstance(v.get('value'),dict) and 'context' in v['value'])
    saved['diagnostic']['fetched_at_epoch']=10**400
    monkeypatch.setenv('PROVIDER_RETRY_ATTEMPTS','1')
    result=EarningsCallProvider().fetch(FetchRequest.from_ticker('6214.TW'))
    assert result.value.get('source')=='TWSE WebPro conference metadata',result.audit
    assert len(upstream[2])==2


@pytest.mark.parametrize('diagnostic', [None, 'not a mapping', [], ['invalid pair']])
def test_malformed_cached_diagnostic_preserves_webpro_fallback(upstream, monkeypatch, diagnostic):
    from systex_conference_index import fetch_systex_conference_context
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    fetch_systex_conference_context('6214.TW')
    saved = next(v['value'] for v in upstream[0].values() if isinstance(v, dict)
                 and isinstance(v.get('value'), dict) and 'context' in v['value'])
    saved['diagnostic'] = diagnostic
    monkeypatch.setenv('PROVIDER_RETRY_ATTEMPTS', '1')
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('6214.TW'))
    assert result.value.get('source') == 'TWSE WebPro conference metadata'
    assert len(upstream[2]) == 2


def test_single_transfer_collector_uses_five_second_hard_deadline(upstream,monkeypatch):
    import systex_conference_transport as transport
    from search_provider_runtime import SourceResponseError
    original=transport.collect_capped_process
    mono=[100.]
    monkeypatch.setattr(transport.time,'monotonic',lambda:mono[0])
    monkeypatch.setattr(transport,'_version',lambda deadline:'8.7.1')
    captured=[]
    def collect(args,deadline,**kwargs):
        captured.append(deadline)
        result=original(args,deadline,**kwargs)
        mono[0]+=6.
        return result
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    with pytest.raises(SourceResponseError):transport.download(transport.HOME_URL,deadline=112.,diagnostics={})
    assert captured[0]<=105.

@pytest.mark.parametrize('warm', [False, True])
def test_original_readback_is_inside_same_twelve_second_operation(upstream,monkeypatch,warm):
    import systex_conference_index as index
    from search_provider_runtime import SourceResponseError
    if warm:
        index.fetch_systex_conference_context('6214.TW')
    mono=[100.]
    monkeypatch.setattr(index.time,'monotonic',lambda:mono[0])
    read=index.read_response
    def delayed(receipt):
        raw=read(receipt);mono[0]+=13.;return raw
    monkeypatch.setattr(index,'read_response',delayed)
    with pytest.raises(SourceResponseError):index.fetch_systex_conference_context('6214.TW')
