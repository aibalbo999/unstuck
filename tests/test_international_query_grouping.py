import asyncio
import pytest
import external_data_gdelt as gdelt

@pytest.mark.parametrize('sector,tag,query',[('', 'macro','("Federal Reserve" OR inflation) when:7d'),('semiconductor','semiconductors_ai','(semiconductor OR "AI chip") when:7d')])
def test_native_fallback_preserves_single_group_and_scope(monkeypatch,sector,tag,query):
 calls=[]
 class Client:
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
 async def fallback(client,actual_tag,actual_query):
  calls.append((actual_tag,actual_query));return []
 monkeypatch.setattr(gdelt,'async_client',lambda:Client())
 monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[])
 monkeypatch.setattr(gdelt,'_gdelt_rate_limited',lambda:True)
 monkeypatch.setattr(gdelt,'cooldown_state',lambda key:{})
 monkeypatch.setattr(gdelt,'_fetch_google_news_rss_fallback',fallback)
 result=asyncio.run(gdelt.fetch_gdelt_international_news_context(sector=sector,max_topics=1))
 assert calls==[(tag,query)]
 assert result['topics']==[] and result['_retrieval']['kind']=='empty'
 assert result['lookback_days']==7
