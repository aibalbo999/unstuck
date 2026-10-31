"""Actual MOPS bounded POST adapter with only the process boundary stubbed."""
from copy import deepcopy
from contextlib import contextmanager
import json,time
import pytest
from test_voltronic_conference import harness,profile,NOW,module
from data_fetch.market_sources import voltronic_conference_transport as t
import mops_material_transport as wire
from search_provider_runtime import SourceResponseError,scope_key
DOWNLOAD=t.ConferenceHttp.download_original

@pytest.fixture
def native(harness,monkeypatch):
 from data_fetch.market_sources import tecom_conference_transport as master
 monkeypatch.setattr(t.ConferenceHttp,'download_original',DOWNLOAD)
 monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
 for k in wire.PROXY_ENV:monkeypatch.delenv(k,raising=False)
 controls={};calls=[]
 def process(args,deadline,**options):
  url=args[-1];raw=harness[0][url];calls.append((args,deadline,options))
  kind='text/csv'if url==t.MASTER_URL else'application/pdf'if url==t.PDF_URL else'text/html'
  status=controls.get('status',200)
  head=(f'HTTP/2 {status}\r\nContent-Type: {kind}\r\nContent-Length: {len(raw)}\r\n'+('Cache-Control: no-cache\r\n'if url==t.MASTER_URL else'')+controls.get('extra','')+'\r\n').encode()
  meta={'http_code':status,'url_effective':url,'num_redirects':0,'size_download':len(raw),'content_type':kind,'method':'GET'if url==t.MASTER_URL else'POST','proxy_used':0};meta.update(controls.get('metadata',{}))
  return {'process_started':True,'body':controls.get('body',raw),'headers':head,'metadata':json.dumps(meta).encode()},controls.get('rc',0),None
 for mod in (wire,master):
  monkeypatch.setattr(mod,'collect_capped_process',process)
  monkeypatch.setattr(mod,'proxy_url_for_request',lambda *a:None)
 return controls,calls

@pytest.mark.parametrize('route',['MASTER_URL','INDEX_URL','PDF_URL'])
def test_native_request_is_exact_bounded_and_replayable(native,route):
 _,calls=native;url=getattr(t,route);deadline=time.monotonic()+25
 raw,r=t.ConferenceHttp(deadline).get_receipt(url);args,stop,options=calls[0]
 assert args[0]=='/usr/bin/curl'and'--location'not in args and'--insecure'not in args
 assert args[args.index('--retry')+1]=='0'and args[args.index('--max-redirs')+1]=='0'
 assert float(args[args.index('--max-time')+1])<={'MASTER_URL':5,'INDEX_URL':5,'PDF_URL':10}[route]
 assert float(args[args.index('--connect-timeout')+1])<=2 and stop<=deadline
 assert options['body_limit']=={'MASTER_URL':2500000,'INDEX_URL':1048576,'PDF_URL':8388608}[route]
 if url!=t.MASTER_URL:assert args[args.index('--data')+1]==r['request_body']==t.request_spec(url)['request_body']and r['request_method']=='POST'
 assert t.original_bytes(r,url,max_age=1800)==raw and r['cache_hit']is False

@pytest.mark.parametrize('change',['length','duplicate','encoding','redirect','method','proxy','truncated','timeout','403','429','challenge'])
def test_failure_keeps_global_cooldown_and_force_cannot_bypass(native,change):
 c,calls=native
 if change=='length':c['body']=b'partial'
 elif change=='duplicate':c['extra']='Content-Length: 1\r\n'
 elif change=='encoding':c['extra']='Content-Encoding: gzip\r\n'
 elif change in ('redirect','method','proxy'):c['metadata']={{'redirect':'num_redirects','method':'method','proxy':'proxy_used'}[change]:{'redirect':1,'method':'GET','proxy':1}[change]}
 elif change=='truncated':c['rc']=18
 elif change=='timeout':c['rc']=28
 elif change=='challenge':c['body']=b'captcha'
 else:c['status']=int(change)
 for opt in ({},{'force_refresh':True},{'use_cache':False}):
  with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,**opt).get_receipt(t.PDF_URL)
 assert len(calls)==1

@pytest.mark.parametrize('route',['global','host','request','failed_cache'])
@pytest.mark.parametrize('options',[{}, {'force_refresh':True}, {'use_cache':False}])
def test_existing_MOPS_guard_blocks_before_master_or_any_HTTP(native,route,options):
 import cache_store
 from mops_material_originals import PREFIX,cache_key
 from hashlib import sha256
 spec=t._descriptor(t.INDEX_URL)
 key={'global':t.GUARD,'host':scope_key(t.HTTP_PROVIDER,endpoint='mopsov.twse.com.tw'),'request':PREFIX+'admission:'+spec['request_sha256'],'failed_cache':'shared_provider:v1:'+sha256(cache_key(spec).encode()).hexdigest()}[route]
 value={'error_kind':'rate_limited','retry_after_epoch':NOW+120}if route=='failed_cache'else{'retry_at':NOW+120}
 cache_store.set_cache_json(key,value,ttl_seconds=120)
 with pytest.raises(SourceResponseError):module('voltronic').fetch_voltronic_context('6409.TW',**options)
 assert not native[1]and cache_store.get_cache_json(key)==value

def test_missing_global_lease_stops_before_HTTP(native,monkeypatch):
 @contextmanager
 def busy(*a,**kw):yield None
 monkeypatch.setattr(t,'endpoint_admission',busy)
 with pytest.raises(SourceResponseError)as caught:t.ConferenceHttp(time.monotonic()+25).get_receipt(t.INDEX_URL)
 assert caught.value.error_kind=='single_flight_busy'and not native[1]

def test_storage_error_stops_before_HTTP(native,monkeypatch):
 import cache_store
 def fail(*a,**k):raise OSError('unavailable')
 monkeypatch.setattr(cache_store,'set_cache_json',fail)
 with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(t.INDEX_URL)
 assert not native[1]

@pytest.mark.parametrize('change',['get','different_file','retime'])
def test_receipt_cannot_be_changed_to_GET_or_another_file_or_epoch(native,change):
 _,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(t.PDF_URL)
 if change=='get':r['request_method']='GET'
 elif change=='different_file':r['request_body']=r['request_body'].replace('E001','M001')
 else:r['retrieved_at']+=1;r['fresh_until_epoch']+=1
 with pytest.raises(ValueError):t.original_bytes(r,t.PDF_URL,max_age=1800)

def test_end_to_end_native_replay_stays_partial_and_uses_three_HTTP(native):
 s=module('voltronic');diag={};v=s.fetch_voltronic_context(s.TICKER,diagnostics=diag)
 assert s.verify_context(v,s.TICKER,max_age=1800)and len(native[1])==diag['http_request_count']==3
 assert v['documents'][0]['page_count']==32 and v['coverage_status']=='partial'

@pytest.mark.parametrize('suffix',['?x=1','/'])
def test_unqualified_URL_never_reaches_HTTP(native,suffix):
 with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(t.PDF_URL+suffix)
 assert not native[1]


@pytest.mark.parametrize('mode',['parsed','raw_only','invalid_html'])
def test_only_parsed_native_content_recovers_expired_MOPS_streak(native,harness,mode):
 import cache_store,search_provider_runtime as runtime
 previous={'consecutive_failures':8,'error_kind':'parse_error','retry_at':NOW-1}
 cache_store.set_cache_json(t.GUARD,previous,ttl_seconds=1000)
 if mode=='invalid_html':
  harness[0][t.INDEX_URL]=b'<html><body>Service maintenance</body></html>'
  with pytest.raises(SourceResponseError)as caught:module('voltronic').fetch_voltronic_context(module('voltronic').TICKER)
  assert caught.value.error_kind=='parse_error'
 elif mode=='raw_only':t.ConferenceHttp(time.monotonic()+25).get_receipt(t.INDEX_URL)
 else:
  value=module('voltronic').fetch_voltronic_context(module('voltronic').TICKER)
  assert value['documents']
 assert cache_store.get_cache_json(t.GUARD)==previous
 assert runtime.remember_failure(t.GUARD,SourceResponseError('parse_error'))['consecutive_failures']==(1 if mode=='parsed'else 9)
