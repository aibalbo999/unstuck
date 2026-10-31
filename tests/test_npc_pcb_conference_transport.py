"""Native bounded transport contracts for each exact issuer host."""
import importlib,json,time
from urllib.parse import urlsplit
import pytest
from test_npc_pcb_conference import harness,profile,PROFILES,NOW,module
T={p:importlib.import_module('data_fetch.market_sources.'+p+'_conference_transport')for p in PROFILES}
DOWNLOAD={p:t.ConferenceHttp.download_original for p,t in T.items()}
@pytest.fixture
def native(profile,harness,monkeypatch):
 t=T[profile];monkeypatch.setattr(t.ConferenceHttp,'download_original',DOWNLOAD[profile]);monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
 for k in t.PROXY_ENV:monkeypatch.delenv(k,raising=False)
 monkeypatch.setattr(t,'proxy_url_for_request',lambda *a:None)
 controls={};calls=[]
 def process(args,deadline,**options):
  url=args[-1];raw=harness[0][url];calls.append((args,deadline,options))
  typ='text/csv'if url==t.MASTER_URL else'application/pdf'if url==t.PDF_URL else'text/html';status=controls.get('status',200)
  cache='no-cache'if url==t.MASTER_URL else''
  headers=(f'HTTP/2 {status}\r\nContent-Type: {typ}\r\nContent-Length: {len(raw)}\r\nCache-Control: {cache}\r\n'+controls.get('extra','')+'\r\n').encode()
  meta={'http_code':status,'url_effective':url,'num_redirects':0,'size_download':len(raw),'content_type':typ,'method':'GET','proxy_used':0};meta.update(controls.get('metadata',{}))
  return {'process_started':True,'body':controls.get('body',raw),'headers':headers,'metadata':json.dumps(meta).encode()},controls.get('rc',0),None
 monkeypatch.setattr(t,'collect_capped_process',process)
 return t,controls,calls

@pytest.mark.parametrize('route',['MASTER_URL','INDEX_URL','PDF_URL'])
def test_native_raw_original_is_accepted_without_relaxing_budget(native,route):
 t,_,calls=native;url=getattr(t,route);deadline=time.monotonic()+25
 raw,r=t.ConferenceHttp(deadline).get_receipt(url);args,stop,opts=calls[0]
 assert args[0]=='/usr/bin/curl'and'--location'not in args and'--insecure'not in args
 assert args[args.index('--retry')+1]=='0'and args[args.index('--max-redirs')+1]=='0'
 assert float(args[args.index('--max-time')+1])<=5 and float(args[args.index('--connect-timeout')+1])<=2
 assert stop<=deadline and opts['body_limit']=={'MASTER_URL':2500000,'INDEX_URL':1048576,'PDF_URL':8388608}[route]
 assert t.original_bytes(r,url,max_age=1800)==raw and r['cache_hit']is False

@pytest.mark.parametrize('change',['length','duplicate','encoding','redirect','method','proxy','truncated','timeout','403','429','challenge'])
def test_rejection_keeps_cooldown_and_no_force_bypass(native,change):
 from search_provider_runtime import SourceResponseError
 t,c,calls=native
 if change=='length':c['body']=b'partial'
 elif change=='duplicate':c['extra']='Content-Length: 1\r\n'
 elif change=='encoding':c['extra']='Content-Encoding: gzip\r\n'
 elif change in ('redirect','method','proxy'):c['metadata']={{'redirect':'num_redirects','method':'method','proxy':'proxy_used'}[change]:{'redirect':1,'method':'POST','proxy':1}[change]}
 elif change=='truncated':c['rc']=18
 elif change=='timeout':c['rc']=28
 elif change=='challenge':c['body']=b'captcha'
 else:c['status']=int(change)
 for opt in ({},{'force_refresh':True},{'use_cache':False}):
  with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,**opt).get_receipt(t.PDF_URL)
 assert len(calls)==1

@pytest.mark.parametrize('guard',[{'retry_at':NOW+120},{'retry_at':True},{'retry_at':float('nan')},{'error_kind':'rate_limited'}])
def test_existing_host_guard_is_not_overridden(native,guard):
 import cache_store
 from search_provider_runtime import SourceResponseError,scope_key
 t,_,calls=native;key=scope_key(t.HTTP_PROVIDER,endpoint=urlsplit(t.INDEX_URL).hostname)
 cache_store.set_cache_json(key,guard,ttl_seconds=120)
 for options in ({},{'force_refresh':True},{'use_cache':False}):
  with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,**options).get_receipt(t.PDF_URL)
 assert not calls

def test_storage_error_stops_before_http(native,monkeypatch):
 import cache_store
 from search_provider_runtime import SourceResponseError
 t,_,calls=native
 def fail(*a,**k):raise OSError('unavailable')
 monkeypatch.setattr(cache_store,'set_cache_json',fail)
 with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(t.INDEX_URL)
 assert not calls

def test_native_source_replay_and_fresh_index_body(native,profile,monkeypatch):
 t,_,calls=native;s=module(profile);fetch=getattr(s,'fetch_'+profile+'_context');v=fetch(s.TICKER)
 assert s.verify_context(v,s.TICKER,max_age=1800)and len(calls)==3
 old=v[profile+'_conference_receipt']['pdf'];monkeypatch.setattr(time,'time',lambda:NOW+10)
 second=fetch(s.TICKER,force_refresh=True)
 assert second['fetched_at_epoch']==NOW+10 and old['retrieved_at']==NOW
 assert sum(args[-1]==t.INDEX_URL for args,_,_ in calls)==2
 assert sum(args[-1]==t.PDF_URL for args,_,_ in calls)==2

@pytest.mark.parametrize('suffix',['?x=1','/'])
def test_unqualified_url_never_reaches_http(native,suffix):
 from search_provider_runtime import SourceResponseError
 t,_,calls=native
 with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(t.PDF_URL+suffix)
 assert not calls

def test_short_upstream_deadline_and_receipt_retiming(native,monkeypatch):
 t,_,calls=native;process=t.collect_capped_process
 def short(*a,**kw):
  p,rc,e=process(*a,**kw);p['headers']=p['headers'].replace(b'Cache-Control: \r\n',b'Cache-Control: max-age=5\r\n');return p,rc,e
 monkeypatch.setattr(t,'collect_capped_process',short);_,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(t.PDF_URL)
 assert r['fresh_until_epoch']==NOW+5
 monkeypatch.setattr(time,'time',lambda:NOW+5)
 with pytest.raises(ValueError):t.original_bytes(r,t.PDF_URL,max_age=1800)
 r['retrieved_at']+=5;r['fresh_until_epoch']+=5
 with pytest.raises(ValueError):t.original_bytes(r,t.PDF_URL,max_age=1800)
