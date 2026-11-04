"""Full response receipts stay separate from issuer/content acceptance."""
from hashlib import sha256
import httpx
import pytest
from provider_correlation import correlation_scope
from data_fetch import annual_workforce_provider as workforce
from data_fetch.annual_occupational_safety import URLS as SAFETY_URLS
from data_fetch.types import FetchRequest
import provider_sla


def observe(monkeypatch, response, url=None):
    events=[]
    monkeypatch.setattr(workforce,'sync_get',lambda *a,**kw:response)
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='native-annual-original'):
        workforce._fetch_dataset(url or workforce.URLS['.TW'])
    return events


@pytest.mark.parametrize('url',[workforce.URLS['.TW'],SAFETY_URLS['.TW']])
def test_complete_original_replays_and_projects_without_private_path(monkeypatch,url):
    from official_response_evidence import read_response
    from provider_observation_details import observation_details
    body=b'[{"not_an_accepted_issuer_fact":true}]'
    response=httpx.Response(200,content=body,request=httpx.Request('GET',url))
    events=observe(monkeypatch,response,url)
    assert len(events)==1
    event=events[0];proof=event['raw_http_receipt']
    assert read_response(proof)==body
    assert proof['evidence_kind']=='decoded_complete_http_response_body'
    assert proof['http_status_observed'] is True and proof['response_complete'] is True
    assert proof['cache_hit'] is False and proof['request_method']=='GET'
    assert event['record_count']==0 and event['response_complete'] is True
    projected=observation_details(event)['original_http_receipts'][0]
    assert projected['response_sha256']==sha256(body).hexdigest()
    assert projected['http_request_sent'] is True and projected['response_complete'] is True
    assert 'raw_response_path' not in str(projected) and body.decode() not in str(projected)


@pytest.mark.parametrize('change',['post','redirect','cached_extension','authorization','proxy-authorization','cookie','partial','length','encoding_length'])
def test_unqualified_response_never_archived_as_complete(monkeypatch,change):
    url=workforce.URLS['.TW'];headers={};request_headers={};status=200
    if change in {'authorization','proxy-authorization','cookie'}:request_headers[change]='private-value'
    if change=='partial':headers['content-range']='bytes 0-1/30';status=206
    if change=='length':headers['content-length']='30'
    if change=='encoding_length':headers.update({'content-encoding':'identity','content-length':'30'})
    response=httpx.Response(status,content=b'[]',headers=headers,
        request=httpx.Request('POST' if change=='post' else 'GET',url,headers=request_headers),
        history=[httpx.Response(302)] if change=='redirect' else [],
        extensions={'from_cache':True} if change=='cached_extension' else {})
    events=observe(monkeypatch,response)
    assert all('raw_http_receipt' not in event for event in events)
    assert all(event.get('response_complete') is not True for event in events)


def test_archive_failure_keeps_bytes_and_transport_receipt(monkeypatch):
    import official_response_evidence
    monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw: (_ for _ in ()).throw(OSError('disk unavailable')))
    url=workforce.URLS['.TW']
    events=observe(monkeypatch,httpx.Response(200,content=b'[]',request=httpx.Request('GET',url)))
    assert len(events)==1 and events[0]['http_status']==200 and events[0]['record_count']==0
    assert 'raw_http_receipt' not in events[0]


def test_research_option_suppresses_receipts_and_archival(monkeypatch):
    import official_response_evidence
    events=[];archives=[];calls=[]
    monkeypatch.setattr(official_response_evidence,'archive_response',lambda *a,**kw:archives.append(1))
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    def fetch(url,**kw):
        calls.append(url);return httpx.Response(200,content=b'[]',request=httpx.Request('GET',url))
    monkeypatch.setattr(workforce,'sync_get',fetch)
    monkeypatch.setattr(workforce,'shared_fetch',lambda key,callback,**kw:(callback(),{'cache_hit':False}))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='research'):
        workforce.AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('1623.TW',record_provider_sla=False))
    assert len(calls)==2 and events==[] and archives==[]


def test_warm_shared_cache_has_no_new_receipt_or_original(monkeypatch):
    events=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    monkeypatch.setattr(workforce,'sync_get',lambda *a,**kw:pytest.fail('warm cache must not fetch'))
    monkeypatch.setattr(workforce,'shared_fetch',lambda key,callback,**kw:('[]',{'cache_hit':True,'fetched_at_epoch':1234}))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='warm'):
        result=workforce.AnnualWorkforceProvider().fetch(FetchRequest.from_ticker('1623.TW'))
    assert events==[] and result.audit['http_request_sent'] is False


def test_unread_stream_is_not_consumed_to_create_evidence(monkeypatch):
    from annual_disclosure_transport import observe_response
    url=workforce.URLS['.TW'];events=[]
    class Unread(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail('Observer must never read a stream')
    response=httpx.Response(200,stream=Unread(),request=httpx.Request('GET',url))
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    with correlation_scope(replace=True,ticker='1623.TW',fetch_id='unread'):
        observe_response(url,response,max_bytes=workforce.MAX_BYTES)
    assert events==[] and not response.is_stream_consumed


def test_false_scope_resets_without_disabling_next_normal_fetch(monkeypatch):
    from annual_disclosure_transport import receipt_observation_scope
    url=workforce.URLS['.TW']
    response=httpx.Response(200,content=b'[]',request=httpx.Request('GET',url))
    with receipt_observation_scope(False):
        assert observe(monkeypatch,response)==[]
    assert len(observe(monkeypatch,response))==1


@pytest.mark.parametrize('headers',[{'cookie':'secret'},{'authorization':'secret'},{'proxy-authorization':'secret'}])
def test_parent_request_metadata_does_not_disagree_with_rejected_native_receipt(headers):
    url=workforce.URLS['.TW']
    response=httpx.Response(200,content=b'[]',request=httpx.Request('GET',url,headers=headers))
    assert workforce._response_request_evidence(url,response)=={}
