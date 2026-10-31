import json
from urllib.parse import urlencode
import provider_sla
from test_international_news_transport import owner,response,Client,call
from external_data_gdelt import GDELT_TOPIC_QUERIES

def test_actual_normal_seven_day_query_archives_without_extra_call(monkeypatch):
    events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    url='https://news.google.com/rss/search?'+urlencode({'q':GDELT_TOPIC_QUERIES['macro']+' when:7d','hl':'en-US','gl':'US','ceid':'US:en'})
    client=Client(response(url=url))
    with owner():out=call(client,'rss',monkeypatch)
    assert len(client.calls)==len(events)==1
    assert events[0]['raw_http_receipt']['status']=='archived'
    assert events[0]['record_count']==0
    assert out==[{'headline':'unchanged result','topic':'macro'}]


import pytest
@pytest.mark.parametrize('tail',[' when:14d',' when:0d',' when:7d PRIVATE',' when:7d when:7d'])
def test_other_windows_or_extra_query_cannot_archive(monkeypatch,tail):
    events=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda rows:events.extend(rows))
    url='https://news.google.com/rss/search?'+urlencode({'q':GDELT_TOPIC_QUERIES['macro']+tail,'hl':'en-US','gl':'US','ceid':'US:en'})
    client=Client(response(url=url))
    with owner():call(client,'rss',monkeypatch)
    assert len(client.calls)==len(events)==1
    assert events[0].get('raw_http_receipt')is None


def test_full_normal_context_builder_retains_actual_window_original(monkeypatch):
    import asyncio,httpx
    import external_data_gdelt as g
    rows=[];requests=[]
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda events:rows.extend(events))
    monkeypatch.setattr(g,'_cached_gdelt_topics',lambda key:[])
    monkeypatch.setattr(g,'_cache_gdelt_topics',lambda *a:None)
    monkeypatch.setattr(g,'cooldown_state',lambda key:{'error_kind':'rate_limited'})
    monkeypatch.setattr(g,'_gdelt_rate_limited',lambda:False)
    def serve(request):
        requests.append(request)
        return httpx.Response(200,content=b'<rss><channel><item><title>Federal Reserve inflation outlook</title><source>Reuters</source><link>https://news.google.com/rss/articles/normal-native-test</link><pubDate>Fri, 30 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>',request=request)
    monkeypatch.setattr(g,'async_client',lambda:httpx.AsyncClient(transport=httpx.MockTransport(serve)))
    with owner():out=asyncio.run(g.fetch_gdelt_international_news_context(max_topics=1))
    assert len(requests)==len(rows)==1
    assert requests[0].url.params['q']==GDELT_TOPIC_QUERIES['macro']+' when:7d'
    assert rows[0]['raw_http_receipt']['status']=='archived'
    assert rows[0]['record_count']==0 and len(out['topics'])==1
    assert out['_retrieval']['fresh_topic_count']==1
