"""Real native command boundary, mocked process only; no live networking."""
import json
import time
from copy import deepcopy
from hashlib import sha256
import pytest
from test_chroma_conference import harness, NOW
from data_fetch.market_sources.chroma_conference_transport import MASTER_URL, INDEX_URL, PDF_URL
from data_fetch.market_sources.chroma_conference_transport import ConferenceHttp
_NATIVE_DOWNLOAD = ConferenceHttp.download_original


@pytest.fixture
def native(monkeypatch,harness):
    from data_fetch.market_sources import chroma_conference_transport as transport
    # Replace the source-fixture seam with the actual native downloader method.
    monkeypatch.setattr(transport.ConferenceHttp,'download_original',_NATIVE_DOWNLOAD)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in transport.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    controls={};calls=[]
    def process(args,deadline,**options):
        url=args[-1];raw=harness[0][url];calls.append((args,deadline,options))
        ctype='text/csv'if url==MASTER_URL else'application/pdf'if url==PDF_URL else'text/html'
        status=controls.get('status',200)
        control='' if url!=MASTER_URL else 'no-cache'
        headers=(f'HTTP/2 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {len(raw)}\r\nCache-Control: {control}\r\n'+controls.get('extra','')+'\r\n').encode()
        meta={'http_code':status,'url_effective':url,'num_redirects':0,'size_download':len(raw),
              'content_type':ctype,'method':'GET','proxy_used':0};meta.update(controls.get('metadata',{}))
        return {'process_started':True,'body':controls.get('body',raw),'headers':headers,'metadata':json.dumps(meta).encode()},controls.get('rc',0),None
    monkeypatch.setattr(transport,'collect_capped_process',process)
    return transport,controls,calls


def test_actual_native_arguments_and_metadata_are_bounded(native):
    t,_,calls=native;d=time.monotonic()+25
    raw,r=t.ConferenceHttp(d).get_receipt(PDF_URL)
    args,stop,options=calls[0]
    assert args[0]=='/usr/bin/curl'and'--location'not in args and'--insecure'not in args
    assert args[args.index('--retry')+1]=='0'and args[args.index('--max-redirs')+1]=='0'
    assert float(args[args.index('--max-time')+1])<=5 and float(args[args.index('--connect-timeout')+1])<=2
    assert stop<=d and options['body_limit']==8*1024*1024
    assert r['response_metadata']['content_length']==len(raw) and r['cache_hit']is False
    assert t.original_bytes(r,PDF_URL,max_age=1800)==raw


def test_native_master_keeps_identity_wire_metadata(native):
    t,_,calls=native
    raw,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(MASTER_URL)
    metadata=r['response_metadata']
    assert metadata['content_encoding']=='identity'
    assert metadata['wire_bytes']==metadata['decoded_bytes']==len(raw)
    assert metadata['wire_sha256']==metadata['decoded_sha256']==sha256(raw).hexdigest()
    assert r['reusable'] is False  # this fixture explicitly publishes no-cache
    assert t.original_bytes(r,MASTER_URL,max_age=1800)==raw
    args,_,options=calls[0]
    assert '--compressed' not in args and options['body_limit']==2_500_000


@pytest.mark.parametrize('extra',['Content-Encoding: gzip\r\n','Content-Length: 1\r\n','Age: invalid\r\n'])
def test_native_master_rejects_encoding_or_ambiguous_metadata(native,extra):
    from search_provider_runtime import SourceResponseError
    t,control,calls=native;control['extra']=extra
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(MASTER_URL)
    assert len(calls)==1


@pytest.mark.parametrize('change',['duplicate','length','encoding','redirect','method','proxy','truncated','challenge','timeout','403','429'])
def test_native_rejection_is_not_success_and_failure_cannot_repeat(native,change):
    from search_provider_runtime import SourceResponseError
    t,controls,calls=native
    if change=='duplicate':controls['extra']='Content-Length: 1\r\n'
    elif change=='length':controls['body']=b'partial'
    elif change=='encoding':controls['extra']='Content-Encoding: gzip\r\n'
    elif change in {'redirect','method','proxy'}:controls['metadata']={ {'redirect':'num_redirects','method':'method','proxy':'proxy_used'}[change]:{'redirect':1,'method':'POST','proxy':1}[change]}
    elif change=='truncated':controls['rc']=18
    elif change=='challenge':controls['body']=b'captcha'
    elif change=='timeout':controls['rc']=28
    else:controls['status']=int(change)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,**options).get_receipt(PDF_URL)
    assert len(calls)==1


def test_storage_failure_blocks_before_http(native,monkeypatch):
    import cache_store
    from search_provider_runtime import SourceResponseError
    t,_,calls=native
    def fail(*a,**k):raise OSError('unwritable isolated guard')
    monkeypatch.setattr(cache_store,'set_cache_json',fail)
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    assert not calls


def test_original_deadline_cannot_be_extended_by_receipt_edit(native,monkeypatch):
    t,_,_=native;_,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    monkeypatch.setattr(time,'time',lambda:NOW+1799)
    r['retrieved_at']+=5;r['fresh_until_epoch']+=5
    with pytest.raises(ValueError):t.original_bytes(r,PDF_URL,max_age=1800)


def test_lock_cleanup_is_inside_transport_delivery_deadline(native,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from search_provider_runtime import SourceResponseError
    t,_,calls=native;clock=[100.]
    @contextmanager
    def lock(*a,**k):
        yield True
        clock[0]=126.
    monkeypatch.setattr(t,'_shared_lock',lock)
    monkeypatch.setattr(t,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    with pytest.raises(SourceResponseError)as caught:t.ConferenceHttp(125).get_receipt(PDF_URL)
    assert caught.value.error_kind=='timeout' and len(calls)==1


def test_active_host_cooldown_is_preserved_for_force(native):
    import cache_store
    from search_provider_runtime import scope_key,SourceResponseError
    t,_,calls=native
    key=scope_key(t.HTTP_PROVIDER,endpoint='www.chromaate.com');state={'retry_at':NOW+120,'reason':'prior429'}
    cache_store.set_cache_json(key,state,ttl_seconds=120)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,**options).get_receipt(PDF_URL)
    assert not calls and cache_store.get_cache_json(key)==state


def test_cleanup_storage_failure_keeps_admission_but_not_discards_original(native,monkeypatch):
    import cache_store
    from search_provider_runtime import SourceResponseError
    t,_,calls=native;real=cache_store.set_cache_json
    def set_value(key,value,*a,**kw):
        if value.get('retry_at')==0:raise OSError('cleanup write failed')
        return real(key,value,*a,**kw)
    monkeypatch.setattr(cache_store,'set_cache_json',set_value)
    http=t.ConferenceHttp(time.monotonic()+25)
    raw,receipt=http.get_receipt(PDF_URL)
    assert receipt['cache_hit']is False and http.components[0]['admission_release_failed']is True
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(PDF_URL)
    assert len(calls)==1


def test_native_index_meta_no_cache_remains_real_http(native,monkeypatch):
    t,_,calls=native
    first=t.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)[1]
    monkeypatch.setattr(time,'time',lambda:NOW+10)
    second=t.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)[1]
    assert len(calls)==2 and first['cache_hit'] is second['cache_hit'] is False
    assert first['response_metadata']['cache_control']==''
    assert second['retrieved_at']==NOW+10 and first['retrieved_at']==NOW


def test_upstream_age_and_hit_are_preserved_without_local_cache_claim(native):
    t,controls,calls=native;controls['extra']='Age: 524970\r\nCF-Cache-Status: HIT\r\n'
    _,receipt=t.ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    assert receipt['response_metadata']['age']==524970
    assert receipt['response_metadata']['cf_cache_status']=='HIT'
    assert receipt['cache_hit'] is False and receipt['retrieved_at']==NOW and len(calls)==1


@pytest.mark.parametrize('header',['Age: invalid\r\n','Pragma: public\r\nPragma: no-cache\r\n','Expires: 1\r\nExpires: 0\r\n'])
def test_issuer_cache_metadata_rejects_invalid_or_duplicate_headers(native,header):
    from search_provider_runtime import SourceResponseError
    t,control,calls=native;control['extra']=header
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)
    assert len(calls)==1


@pytest.mark.parametrize('row',[{},'bad',{'error_kind':'rate_limited'},{'retry_at':True},{'retry_at':float('nan')}])
def test_malformed_host_guard_fails_closed_before_native(native,row):
    import cache_store
    from search_provider_runtime import scope_key,SourceResponseError
    t,_,calls=native
    cache_store.set_cache_json(scope_key(t.HTTP_PROVIDER,endpoint='www.chromaate.com'),row,ttl_seconds=120)
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)
    assert not calls


def test_positive_short_upstream_validation_ttl_does_not_extend_at_readback(native,monkeypatch):
    t,control,_=native
    # Native helper fixture has one Cache-Control line; replace it at the process seam.
    process=t.collect_capped_process
    def short(*a,**kw):
        parts,rc,err=process(*a,**kw);parts['headers']=parts['headers'].replace(b'Cache-Control: \r\n',b'Cache-Control: max-age=5\r\n');return parts,rc,err
    monkeypatch.setattr(t,'collect_capped_process',short)
    _,receipt=t.ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    assert receipt['fresh_until_epoch']==NOW+5
    monkeypatch.setattr(time,'time',lambda:NOW+5)
    with pytest.raises(ValueError):t.original_bytes(receipt,PDF_URL,max_age=1800)


def test_real_csv_timeout_gzip_json_master_path_and_warm_identity_keep_fresh_bodies(native,monkeypatch):
    from data_fetch.market_sources import official_issuer_master_json as js, chroma_conference as source
    from test_chroma_conference import ROOT
    t,_,calls=native;normal=t.collect_capped_process
    R=ROOT/'docs/evidence/source-acquisition/20261014/issuer-master-reliability/compression-research'
    wire=(R/'json.wire').read_bytes();js_calls=[]
    def csv_timeout(args,deadline,**kw):
        if args[-1]==MASTER_URL:
            calls.append((args,deadline,kw))
            return {'process_started':True,'body':b'','headers':b'','metadata':json.dumps({'http_code':0}).encode()},28,None
        return normal(args,deadline,**kw)
    def json_original(args,deadline,**kw):
        assert args[-1]==js.URL and 'Accept-Encoding: gzip' in args
        js_calls.append(args)
        headers=f'HTTP/2 200\r\nContent-Type: application/json\r\nContent-Encoding: gzip\r\nContent-Length: {len(wire)}\r\n\r\n'.encode()
        metadata={'http_code':200,'url_effective':js.URL,'num_redirects':0,'size_download':len(wire),'content_type':'application/json','method':'GET','proxy_used':0}
        return {'process_started':True,'body':wire,'headers':headers,'metadata':json.dumps(metadata).encode()},0,None
    monkeypatch.setattr(t,'collect_capped_process',csv_timeout)
    monkeypatch.setattr(js,'collect_capped_process',json_original)
    monkeypatch.setattr(js,'proxy_url_for_request',lambda *a:None)
    d={};value=source.fetch_chroma_context('2360.TW',diagnostics=d)
    assert d['http_request_count']==4 and len(js_calls)==1
    r=value['chroma_conference_receipt']['identity']
    assert r['source_url']==js.URL and r['response_metadata']['content_encoding']=='gzip' and r['cache_hit'] is False
    assert source.verify_context(value,'2360.TW',max_age=1800)
    monkeypatch.setattr(time,'time',lambda:NOW+10);d={}
    again=source.fetch_chroma_context('2360.TW',diagnostics=d,force_refresh=True)
    assert d['http_request_count']==2 and len(js_calls)==1
    assert again['chroma_conference_receipt']['identity']['retrieved_at']==NOW
    assert again['chroma_conference_receipt']['identity']['cache_hit'] is True
    assert again['fetched_at_epoch']==NOW+10 and d['cache_hit'] is False


@pytest.mark.parametrize('url,budget',[(MASTER_URL,5.),(INDEX_URL,5.),(PDF_URL,5.)])
def test_exact_route_native_budget_keeps_other_originals_at_five_seconds(native,monkeypatch,url,budget):
    from types import SimpleNamespace
    t,_,calls=native
    monkeypatch.setattr(time,'monotonic',lambda:100.)
    monkeypatch.setattr(t,'time',SimpleNamespace(monotonic=lambda:100.,time=lambda:NOW))
    t.ConferenceHttp(125.).get_receipt(url)
    args,stop,_=calls[0]
    assert len(calls)==1 and float(args[args.index('--max-time')+1])==budget
    assert stop==100.+budget and float(args[args.index('--connect-timeout')+1])==2.


@pytest.mark.parametrize('remaining',[1.5,3.,5.])
def test_pdf_budget_never_exceeds_remaining_whole_deadline_or_accepts_late_bytes(native,monkeypatch,remaining):
    from types import SimpleNamespace
    import cache_store
    from search_provider_runtime import SourceResponseError
    t,_,calls=native;clock=[100.];process=t.collect_capped_process
    monkeypatch.setattr(t,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:NOW))
    def late(args,stop,**kw):
        result=process(args,stop,**kw)
        assert float(args[args.index('--max-time')+1])==remaining
        assert float(args[args.index('--connect-timeout')+1])==min(2.,remaining)
        assert stop==100.+remaining
        clock[0]=stop
        return result
    monkeypatch.setattr(t,'collect_capped_process',late)
    http=t.ConferenceHttp(100.+remaining)
    with pytest.raises(SourceResponseError) as caught:http.get_receipt(PDF_URL)
    assert caught.value.error_kind=='timeout' and len(calls)==http.http_request_count==1
    assert 'original_receipt' not in http.components[0]
    guard=cache_store.get_cache_json(http._admission_key(PDF_URL))
    assert guard['retry_at']==NOW+120
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):t.ConferenceHttp(clock[0]+25,**options).get_receipt(PDF_URL)
    assert len(calls)==1 and cache_store.get_cache_json(http._admission_key(PDF_URL))==guard


@pytest.mark.parametrize('url',[PDF_URL+'?x=1',PDF_URL+'/',PDF_URL.replace('20260730','20260731')])
def test_pdf_budget_does_not_admit_other_urls(native,url):
    from search_provider_runtime import SourceResponseError
    t,_,calls=native
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(url)
    assert not calls

@pytest.mark.parametrize('change',['visible_challenge','different_script','incomplete_index'])
def test_recaptcha_asset_exception_never_accepts_a_challenge_or_unqualified_index(native,harness,change):
    from search_provider_runtime import SourceResponseError
    t,_,calls=native;raw=harness[0][INDEX_URL]
    asset=b"<script src='https://www.google.com/recaptcha/api.js?hl=zh-tw'></script>"
    assert asset in raw
    if change=='visible_challenge':raw=raw.replace(asset,b'<p>Access denied: solve CAPTCHA</p>'+asset)
    elif change=='different_script':raw=raw.replace(asset,asset.replace(b'hl=zh-tw',b'hl=en'))
    else:raw=b'<html><head>'+asset+b'</head><body>captcha required</body></html>'
    harness[0][INDEX_URL]=raw
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(INDEX_URL)
    assert len(calls)==1
