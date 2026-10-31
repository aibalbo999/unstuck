from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import time
import pytest
from test_pcsc_conference import harness, NOW, MASTER, INDEX, PROFILE, PDF

@contextmanager
def raises_kind(kind):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError) as error:yield error
    assert error.value.error_kind==kind


def test_arbitrary_pdf_or_profile_not_authorized_before_complete_index(harness):
    from data_fetch.market_sources.pcsc_conference_transport import PcscConferenceHttp
    from search_provider_runtime import SourceResponseError
    http=PcscConferenceHttp(time.monotonic()+20)
    for url in (PROFILE,PDF,PDF.replace('/262/','/999/'),'https://ir.7-11.com.tw/tw/event.php?year=2027'):
        with raises_kind('transport_url_invalid'):http.get_receipt(url)
    assert not harness[1]
    raw,receipt=http.get_receipt(INDEX)
    wrong=deepcopy(receipt);wrong['retrieved_at']-=1
    with raises_kind('original_unverified'):http.authorize_index_links(wrong)
    selected=http.authorize_index_links(receipt)
    assert selected['pdf_url']==PDF
    with raises_kind('transport_url_invalid'):http.get_receipt(PDF.replace('/262/','/999/'))


@pytest.mark.parametrize('status',[401,403,429,500,302])
def test_native_denial_or_redirect_never_retried_and_counts_actual_http(harness,monkeypatch,status):
    from data_fetch.market_sources import pcsc_conference_transport as t
    from search_provider_runtime import SourceResponseError
    calls=[]
    def process(args,deadline,**opts):
        calls.append(args[-1])
        return {'body':b'denied','headers':f'HTTP/2 {status}\r\nContent-Type: text/html\r\nRetry-After: 120\r\n\r\n'.encode(),
                'metadata':json.dumps({'http_code':status}).encode(),'process_started':True},0,None
    monkeypatch.setattr(t,'collect_capped_process',process)
    http=t.PcscConferenceHttp(time.monotonic()+20)
    with pytest.raises(SourceResponseError):http.get_receipt(INDEX)
    assert calls==[INDEX] and http.http_request_count==1
    assert http.components[-1]['http_status']==status
    with pytest.raises(SourceResponseError):http.get_receipt(INDEX)
    assert calls==[INDEX]


@pytest.mark.parametrize('kind',['admission','raw','host','storage'])
def test_malformed_or_unavailable_guards_fail_before_http(harness,monkeypatch,kind):
    import cache_store
    from data_fetch.market_sources import pcsc_conference_transport as t
    from search_provider_runtime import SourceResponseError,scope_key
    http=t.PcscConferenceHttp(time.monotonic()+20)
    if kind=='admission':key=http._admission_key(INDEX)
    elif kind=='raw':key='shared_provider:v1:'+sha256((http.raw_cache_prefix+INDEX).encode()).hexdigest()
    else:key=scope_key(t.HTTP_PROVIDER,endpoint='ir.7-11.com.tw')
    if kind=='storage':monkeypatch.setattr(cache_store,'get_cache_json',lambda *a,**kw:(_ for _ in ()).throw(OSError('unavailable')))
    else:cache_store.set_cache_json(key,{'unknown':True},ttl_seconds=120)
    with raises_kind('guard_storage_unavailable'):http.get_receipt(INDEX)
    assert not harness[1] and http.http_request_count==0


def test_native_flags_and_shorter_ttl_manifest_are_preserved(harness,monkeypatch):
    from data_fetch.market_sources import pcsc_conference_transport as t
    from search_provider_runtime import SourceResponseError
    original=t.collect_capped_process;args_seen=[]
    def native(args,deadline,**opts):
        args_seen.append((args,opts))
        parts,rc,err=original(args,deadline,**opts)
        parts['headers']=parts['headers'].replace(b'\r\n\r\n',b'\r\nCache-Control: private, max-age=5\r\nAge: 1\r\n\r\n')
        return parts,rc,err
    monkeypatch.setattr(t,'collect_capped_process',native)
    http=t.PcscConferenceHttp(time.monotonic()+20)
    raw,proof=http.get_receipt(INDEX)
    args,opts=args_seen[0]
    assert float(args[args.index('--max-time')+1])<=5 and float(args[args.index('--connect-timeout')+1])<=2
    assert args[args.index('--max-redirs')+1]=='0' and args[args.index('--retry')+1]=='0'
    assert args[args.index('--proto')+1]=='=https' and '-k' not in args and '--location' not in args
    assert opts['body_limit']==1048576 and proof['fresh_until_epoch']==NOW+4
    assert proof['retrieval_policy']=='always_native_no_success_cache' and proof['cache_hit'] is False
    assert t.original_bytes(proof,INDEX)==raw
    monkeypatch.setattr(time,'time',lambda:NOW+4.1)
    with pytest.raises(ValueError):t.original_bytes(proof,INDEX)


def test_duplicate_header_no_fabricated_http_or_success(harness,monkeypatch):
    from data_fetch.market_sources import pcsc_conference_transport as t
    from search_provider_runtime import SourceResponseError
    original=t.collect_capped_process
    def native(*args,**kwargs):
        parts,rc,err=original(*args,**kwargs)
        parts['headers']=parts['headers'].replace(b'\r\n\r\n',b'\r\nContent-Length: 1\r\n\r\n')
        return parts,rc,err
    monkeypatch.setattr(t,'collect_capped_process',native)
    http=t.PcscConferenceHttp(time.monotonic()+20)
    with raises_kind('transport_metadata_invalid'):http.get_receipt(INDEX)
    assert http.http_request_count==1 and http.components[0]['http_status']==200
    assert http.components[0]['error_kind']=='transport_metadata_invalid' and 'original_receipt' not in http.components[0]


def test_lease_not_written_cannot_start_native(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import pcsc_conference_transport as t
    monkeypatch.setattr(cache_store,'set_cache_json',lambda *a,**k:None)
    http=t.PcscConferenceHttp(time.monotonic()+20)
    with raises_kind('lease_lost'):http.get_receipt(INDEX)
    assert not harness[1] and http.http_request_count==0


def test_expired_source_deadline_cannot_start_native(harness):
    from data_fetch.market_sources import pcsc_conference_transport as t
    http=t.PcscConferenceHttp(time.monotonic()-1)
    with raises_kind('timeout'):http.get_receipt(INDEX)
    assert not harness[1]
