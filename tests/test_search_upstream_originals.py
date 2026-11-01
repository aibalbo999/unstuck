import httpx,pytest
import search_upstream_original as source
@pytest.mark.parametrize('damage',[None,'status','cache','cookie','provider','context','xml','credentials','outside_scope','job','fingerprint','source_owner'])
def test_original_receipt_requires_exact_owned_native_public_rss(monkeypatch,damage):
 import provider_correlation,official_response_evidence
 context={'ticker':'2367.TW','fetch_id':'f','operation_id':'o','attempt_id':'a'}
 monkeypatch.setattr(provider_correlation,'current_correlation',lambda:dict(context))
 calls=[]
 def archive(body,**kw):
  import hashlib
  calls.append(body);return {'status':'archived','raw_response_sha256':hashlib.sha256(body).hexdigest(),'raw_response_bytes':len(body)}
 monkeypatch.setattr(official_response_evidence,'archive_response',archive)
 params={'q':'2367','hl':'zh-TW','gl':'TW','ceid':'TW:zh-Hant'}
 if damage=='credentials':params['token']='secret'
 request=httpx.Request('GET','https://news.google.com/rss/search',params=params,headers={'cookie':'x'}if damage=='cookie'else{})
 response=httpx.Response(429 if damage=='status'else 200,content=b'<rss><channel/></rss>'if damage!='xml'else b'<!DOCTYPE rss><rss><channel/></rss>',request=request)
 if damage=='cache':response.extensions['from_cache']=True
 if damage=='outside_scope':
  source.capture(response,'google_news_rss');assert not calls;return
 with source.capture_scope('google_news_rss','search')as capsule:
  if damage=='context':context['attempt_id']='different'
  elif damage=='job':context['job_id']='other-job'
  elif damage=='fingerprint':context['data_fingerprint']='a'*64
  elif damage=='source_owner':monkeypatch.setattr(provider_correlation,'current_source_identity',lambda:('other','provider'))
  source.capture(response,'bing_news_rss'if damage=='provider'else'google_news_rss')
  assert bool(capsule['evidence'])==(damage is None)
 assert bool(calls)==(damage is None)
 assert source._ACTIVE.get()is None

def test_archive_exception_never_escapes_or_leaks_scope(monkeypatch):
 import provider_correlation,official_response_evidence
 monkeypatch.setattr(provider_correlation,'current_correlation',lambda:{'ticker':'2367.TW','fetch_id':'f','operation_id':'o','attempt_id':'a'})
 def fail(*a,**kw):raise OSError('unavailable')
 monkeypatch.setattr(official_response_evidence,'archive_response',fail)
 request=httpx.Request('GET','https://www.bing.com/news/search',params={'q':'2367','format':'rss'})
 response=httpx.Response(200,content=b'<rss><channel/></rss>',request=request)
 with source.capture_scope('bing_news_rss','search')as capsule:
  source.capture(response,'bing_news_rss');assert capsule['evidence']=={}
 assert source._ACTIVE.get()is None

@pytest.mark.parametrize('provider',['google_news_rss','bing_news_rss'])
@pytest.mark.parametrize('archive_fails',[False,True])
def test_existing_request_path_adds_receipt_to_single_original_observation(monkeypatch,provider,archive_fails):
 import asyncio
 from contextlib import asynccontextmanager
 import search_provider_runtime as runtime,external_search_provider_clients as clients
 import official_response_evidence
 from provider_correlation import correlation_scope
 @asynccontextmanager
 async def admission(*a,**kw):yield lambda:True
 monkeypatch.setattr(runtime,'async_endpoint_admission',admission)
 state={};events=[];sends=[]
 monkeypatch.setattr(runtime,'get_cache_json',lambda key:state.get(key))
 monkeypatch.setattr(runtime,'set_cache_json',lambda key,value,**kw:state.__setitem__(key,value))
 monkeypatch.setattr(runtime,'provider_circuit_state',lambda key:{})
 monkeypatch.setattr(runtime,'record_source_audit_entries',lambda rows:events.extend(rows))
 if archive_fails:
  def fail(*a,**kw):raise OSError('unavailable')
  monkeypatch.setattr(official_response_evidence,'archive_response',fail)
 body=b'<rss><channel><item><title>Company update</title><source>Publisher</source><link>https://publisher.test/a</link><pubDate>Fri, 30 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>'
 def handler(request):sends.append(request);return httpx.Response(200,content=body,request=request)
 async def run():
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler))as client:
   with correlation_scope(replace=True,ticker='2367.TW',fetch_id='fetch',operation_id='operation'):
    async def callback():return await clients.fetch_provider_results(client,provider,'2367',max_results=3,lookback_days=30)
    return await runtime.fetch_search_upstream(provider,'',callback)
 records=asyncio.run(run())
 assert len(records)==1 and len(sends)==1 and len(events)==1
 event=events[0];assert event['provider']==provider and event['record_count']==1 and event['source']=='search_upstream'
 assert event['http_request_sent']is True and event['ticker']=='2367.TW'
 assert bool(event.get('raw_http_receipt'))is (not archive_fails)
 from provider_observation_details import observation_details
 projected=observation_details(event)
 assert bool(projected.get('original_http_receipts'))is (not archive_fails)
 if not archive_fails:
  receipt=projected['original_http_receipts'][0]
  assert receipt['http_request_sent']is True and receipt['http_status_observed']is True
  assert receipt['response_complete']is True and receipt['original_cache_hit']is False
  assert receipt['response_sha256']==event['response_sha256']
  assert 'raw_response_path'not in projected and 'source_url'not in projected
  from official_response_evidence import read_response
  archived=read_response(event['raw_http_receipt'],max_bytes=2_000_000)
  assert archived==body
  assert clients.parse_news_rss_payload(archived.decode(),provider=provider,fallback_source='unused')==records
 assert source._ACTIVE.get()is None

def test_parallel_callbacks_keep_context_and_originals_separate(monkeypatch):
 import asyncio,hashlib
 from provider_correlation import correlation_scope
 import official_response_evidence
 saved=[]
 def archive(body,**kw):
  digest=hashlib.sha256(body).hexdigest();saved.append(digest)
  return {'status':'archived','raw_response_sha256':digest,'raw_response_bytes':len(body)}
 monkeypatch.setattr(official_response_evidence,'archive_response',archive)
 async def worker(ticker,provider):
  with correlation_scope(replace=True,ticker=ticker,fetch_id='f'+ticker,operation_id='o'+ticker,attempt_id='a'+ticker):
   with source.capture_scope(provider,'search')as capsule:
    await asyncio.sleep(0)
    url='https://news.google.com/rss/search'if provider=='google_news_rss'else'https://www.bing.com/news/search'
    params={'q':ticker,'hl':'zh-TW','gl':'TW','ceid':'TW:zh-Hant'}if provider=='google_news_rss'else{'q':ticker,'format':'rss'}
    body=('<rss><channel><title>'+ticker+'</title></channel></rss>').encode()
    response=httpx.Response(200,content=body,request=httpx.Request('GET',url,params=params))
    source.capture(response,provider);await asyncio.sleep(0)
    assert capsule['context']['ticker']==ticker
    assert capsule['evidence']['response_sha256']==hashlib.sha256(body).hexdigest()
    return capsule['evidence']['response_sha256']
 async def run():return await asyncio.gather(worker('2367.TW','google_news_rss'),worker('3017.TW','bing_news_rss'))
 hashes=asyncio.run(run());assert len(set(hashes))==2 and set(hashes)==set(saved)
 assert source._ACTIVE.get()is None

def test_cancelled_callback_does_not_leak_original_scope():
 import asyncio
 from provider_correlation import correlation_scope
 async def worker():
  with correlation_scope(replace=True,ticker='2367.TW',fetch_id='f',operation_id='o',attempt_id='a'):
   try:
    with source.capture_scope('google_news_rss','search'):
     raise asyncio.CancelledError()
   except asyncio.CancelledError:
    assert source._ACTIVE.get()is None
    raise
 with pytest.raises(asyncio.CancelledError):asyncio.run(worker())
 assert source._ACTIVE.get()is None

def test_multiple_responses_cannot_leave_a_single_misleading_receipt(monkeypatch):
 import provider_correlation,official_response_evidence,hashlib
 monkeypatch.setattr(provider_correlation,'current_correlation',lambda:{'ticker':'2367.TW','fetch_id':'f','operation_id':'o','attempt_id':'a'})
 calls=[]
 def archive(body,**kw):calls.append(body);return {'status':'archived','raw_response_sha256':hashlib.sha256(body).hexdigest(),'raw_response_bytes':len(body)}
 monkeypatch.setattr(official_response_evidence,'archive_response',archive)
 response=httpx.Response(200,content=b'<rss><channel/></rss>',request=httpx.Request('GET','https://www.bing.com/news/search',params={'q':'2367','format':'rss'}))
 with source.capture_scope('bing_news_rss','search')as capsule:
  source.capture(response,'bing_news_rss');assert capsule['evidence']
  source.capture(response,'bing_news_rss');assert capsule['evidence']=={}
  source.capture(response,'bing_news_rss');assert capsule['evidence']=={}
 assert len(calls)==1
