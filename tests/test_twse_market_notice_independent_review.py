"""Independent public-boundary review; external transport and temp cache only."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import base64,json,time
import pytest

RAW=(Path(__file__).parent/'fixtures/source_acquisition/twse_allmarket_notices_20261014.json').read_bytes()
NOW=datetime(2026,10,14,4,5,tzinfo=ZoneInfo('Asia/Taipei'))

@pytest.fixture
def boundary(monkeypatch):
 import cache_store
 from cache_backends import InMemoryCache
 import data_fetch.market_sources.twse_market_trading_notices as module
 from data_fetch.market_sources.issuer_news_transport import IssuerNewsHttp
 cache_store.set_cache_backend(InMemoryCache())
 epoch=[NOW.timestamp()];calls=[]
 monkeypatch.setattr(time,'time',lambda:epoch[0])
 class FixedDate(datetime):
  @classmethod
  def now(cls,tz=None):return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)
 monkeypatch.setattr(module,'datetime',FixedDate)
 def download(self,url,diagnostic):
  calls.append(url);self.http_request_count+=1
  diagnostic.update(http_request_sent=True,http_status=200)
  return {'url':url,'body_b64':base64.b64encode(RAW).decode(),'sha256':sha256(RAW).hexdigest()}
 monkeypatch.setattr(IssuerNewsHttp,'_download',download)
 yield module,epoch,calls
 cache_store.reset_cache_store_for_tests()

def fetch(ticker):
 from data_fetch.trading_notices_provider import TradingNoticesProvider
 from data_fetch.types import FetchRequest
 return TradingNoticesProvider().fetch(FetchRequest.from_ticker(ticker),{'data':{'ticker':ticker}})

def test_review_cold_warm_empty_have_distinct_acquisition_truth(boundary):
 from provider_acquisition import observation_kind
 module,epoch,calls=boundary
 results=[fetch(t)for t in ['6504.TW','6531.TW','1216.TW']]
 kinds=[]
 for r in results:
  kinds.append(observation_kind({'provider':r.provider,'status':r.status,'record_count':r.audit['record_count'],'message':r.audit['message'],'details':r.audit}))
 assert len(calls)==1
 assert kinds==['fetched_count','fresh_cache_count','empty_cache_count']
 assert [r.audit['http_request_count']for r in results]==[1,0,0]
 assert {r.audit['fetched_at_epoch']for r in results}=={epoch[0]}

@pytest.mark.parametrize('change',['http_unobserved','cache_only_metadata','wrong_original_length'])
def test_review_conflicting_native_receipt_cannot_be_accepted(boundary,change):
 from source_content_selection import issuer_match
 r=deepcopy(fetch('6504.TW').value[0]);receipt=r['trading_notice_receipt']['original']
 if change=='http_unobserved':receipt['http_status_observed']=False
 elif change=='cache_only_metadata':receipt['cache_source']='shared_listed_roster';receipt['http_status_observed']=False
 else:receipt['raw_response_bytes']=1
 assert issuer_match(r,{'ticker':'6504.TW'}) is None

def test_review_final_handoff_honors_explicit_shorter_raw_cache_expiry(boundary,monkeypatch):
 import cache_store
 module,epoch,calls=boundary
 first=fetch('6504.TW');assert first.status=='success'
 key='shared_provider:v1:'+sha256(('issuer-news-raw:v1:'+module.source_url(NOW)).encode()).hexdigest()
 original=cache_store.get_cache_json(key);original['fresh_until_epoch']=epoch[0]+0.5
 cache_store.set_cache_json(key,original,ttl_seconds=1800)
 verifier=module.verified_market_record
 def slow(*args,**kwargs):
  result=verifier(*args,**kwargs);epoch[0]+=0.6;return result
 monkeypatch.setattr(module,'verified_market_record',slow)
 second=fetch('6531.TW')
 assert epoch[0]>original['fresh_until_epoch']
 assert second.value==[] and second.status=='error'
 assert second.audit['http_request_count']==0 and len(calls)==1

def test_review_cross_ticker_saved_record_rejected(boundary):
 from source_content_selection import issuer_match
 row=deepcopy(fetch('6504.TW').value[0]);row['ticker']='6531.TW'
 assert issuer_match(row,{'ticker':'6531.TW'}) is None

def test_review_cold_archive_can_deliver_when_shared_cache_write_fails(boundary,monkeypatch):
 import cache_store
 from source_content_selection import issuer_match
 def unavailable(*args,**kwargs):raise OSError('isolated shared cache write unavailable')
 monkeypatch.setattr(cache_store,'set_cache_json',unavailable)
 result=fetch('6504.TW')
 assert result.status=='success' and result.value
 assert result.audit['http_request_count']==1 and result.audit['cache_hit'] is False
 assert all(issuer_match(row,{'ticker':'6504.TW'})=='6504' for row in result.value)

def test_review_warm_shared_row_disappearing_before_expiry_admission_fails_closed(boundary,monkeypatch):
 import cache_store
 module,epoch,calls=boundary
 assert fetch('6504.TW').status=='success'
 real_get=cache_store.get_cache_json;seen=[]
 def disappear(key,*args,**kwargs):
  seen.append(key)
  return real_get(key,*args,**kwargs) if len(seen)==1 else None
 monkeypatch.setattr(cache_store,'get_cache_json',disappear)
 result=fetch('6531.TW')
 assert len(seen)==2 and result.status=='error' and not result.value
 assert result.audit['http_request_count']==0 and result.audit['cache_hit'] is False and len(calls)==1
