"""Bound original bytes to one existing public RSS callback; never send or count."""
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlsplit,parse_qs
import re,time
_ACTIVE=ContextVar('public_search_original',default=None)
ENDPOINTS={'google_news_rss':('news.google.com','/rss/search'),'bing_news_rss':('www.bing.com','/news/search')}
@contextmanager
def capture_scope(provider,endpoint):
 from provider_correlation import current_correlation,current_source_identity
 capsule={'provider':provider,'endpoint':endpoint,'context':dict(current_correlation()),'source_identity':current_source_identity(),'evidence':{},'seen_responses':0}
 token=_ACTIVE.set(capsule)
 try:yield capsule
 finally:_ACTIVE.reset(token)

def capture(response,provider):
 try:
  import httpx
  from provider_correlation import current_correlation,current_source_identity
  from official_response_evidence import archive_response
  from xml.etree.ElementTree import fromstring
  cap=_ACTIVE.get()
  if not cap or cap['provider']!=provider or cap['endpoint']!='search' or provider not in ENDPOINTS:return
  context=current_correlation()
  if current_source_identity()!=cap['source_identity']:return
  if any(context.get(k)!=cap['context'].get(k)for k in ('job_id','data_fingerprint')):return
  if any(not context.get(k) or context.get(k)!=cap['context'].get(k)for k in ('ticker','fetch_id','operation_id','attempt_id')):return
  if not re.fullmatch(r'(?:[0-9]{4,6}\.TW(?:O)?|[A-Z][A-Z0-9.\-]{0,14})',context['ticker']):return
  cap['seen_responses']+=1
  if cap['seen_responses']!=1:
   cap['evidence']={}
   return
  if type(response)is not httpx.Response or response.status_code!=200 or response.history:return
  request=response.request;url=urlsplit(str(response.url));query=parse_qs(url.query,keep_blank_values=True)
  if (request.method!='GET' or str(request.url)!=str(response.url)or url.scheme!='https'or url.username or url.password or url.fragment or url.port not in (None,443)or (url.hostname,url.path)!=ENDPOINTS[provider]
      or getattr(response,'from_cache',False)or response.extensions.get('from_cache')is True
      or any(request.headers.get(k)for k in ('authorization','cookie','proxy-authorization'))):return
  if provider=='google_news_rss':
   if set(query)!={'q','hl','gl','ceid'}or query['hl']!=['zh-TW']or query['gl']!=['TW']or query['ceid']!=['TW:zh-Hant']:return
  elif set(query)!={'q','format'}or query['format']!=['rss']:return
  if len(query.get('q',[]))!=1 or not query['q'][0]or len(query['q'][0])>1000:return
  body=response.content
  if (not isinstance(body,bytes)or not 0<len(body)<=2_000_000 or b'\x00'in body or b'<!DOCTYPE'in body.upper()or b'<!ENTITY'in body.upper()):return
  root=fromstring(body)
  if root.tag!='rss'or root.find('channel')is None:return
  host,path=ENDPOINTS[provider]
  proof=archive_response(body,source_url='https://'+host+path,retrieved_at=time.time(),evidence_kind='decoded_complete_http_response_body',max_bytes=2_000_000)
  if proof.get('status')!='archived':return
  proof.update(http_status_observed=True,response_complete=True,request_method='GET',cache_hit=False)
  cap['evidence']={'response_sha256':proof['raw_response_sha256'],'response_bytes':proof['raw_response_bytes'],'raw_http_receipt':proof}
 except Exception:return
