import sys,asyncio,importlib.util
from pathlib import Path
sys.path.insert(0,'/Volumes/X10 Pro Mac/stock-agent/backend')
import data_fetch
from data_fetch.types import FetchRequest,ProviderResult
from provider_correlation import correlation_scope,current_correlation,current_source_identity
import data_fetch.radar as radar
def test_one_radar_provider_call_gets_native_owner_and_restores_parent():
 calls=[];value={'topics':[{'title':'sample'}]};original=ProviderResult(source='international_news_context',provider='GDELT / Google News RSS',status='success',value=value,audit={'status':'success'})
 class Provider:
  source='international_news_context';name='GDELT / Google News RSS'
  async def fetch_async(self,request,context):
   calls.append(context)
   assert current_source_identity()==(self.source,self.name)
   assert current_correlation().get('operation_id')
   return original
 class Registry:
  def first_provider(self,*args):return Provider()
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='parent'):
  before=current_correlation();result=asyncio.run(radar.fetch_radar_payload(FetchRequest.from_ticker('2330.TW'),('international_news_context',),Registry()))
  assert current_correlation()==before and current_source_identity()is None
 assert calls==[{'original_ticker':'2330.TW'}]
 assert result['international_news_context']==value
 assert result['source_audit'][0]['fetch_id']=='parent'and result['source_audit'][0]['operation_id']
 assert original.audit=={'status':'success'}

import pytest

@pytest.mark.parametrize('error_type',[RuntimeError,asyncio.CancelledError])
def test_provider_failure_restores_parent_without_retry(error_type):
 calls=[]
 class Provider:
  source='international_news_context';name='GDELT / Google News RSS'
  async def fetch_async(self,request,context):
   calls.append(context)
   assert current_source_identity()==(self.source,self.name)
   raise error_type('expected failure')
 class Registry:
  def first_provider(self,*args):return Provider()
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='parent'):
  before=current_correlation()
  with pytest.raises(error_type):
   asyncio.run(radar.fetch_radar_payload(FetchRequest.from_ticker('2330.TW'),('international_news_context',),Registry()))
  assert current_correlation()==before and current_source_identity()is None
 assert len(calls)==1

@pytest.mark.parametrize('old_audit',[
 {'fetch_id':'historical','cache_hit':True,'stale':False,'timestamp':'2026-10-30T01:00:00Z'},
 {'operation_id':'historical-operation','cache_hit':True,'stale':False},
])
def test_historical_cache_audit_is_not_rebound(old_audit):
 value={'topics':[{'title':'retained metadata'}]}
 original=ProviderResult(source='international_news_context',provider='GDELT / Google News RSS',status='success',value=value,audit=dict(old_audit))
 class Provider:
  source='international_news_context';name='GDELT / Google News RSS'
  async def fetch_async(self,request,context):return original
 class Registry:
  def first_provider(self,*args):return Provider()
 with correlation_scope(replace=True,ticker='2330.TW',fetch_id='new-fetch'):
  result=asyncio.run(radar.fetch_radar_payload(FetchRequest.from_ticker('2330.TW'),('international_news_context',),Registry()))
 assert result['source_audit']==[old_audit]
 assert original.audit==old_audit
 assert result['international_news_context']==value
