from copy import deepcopy
from provider_correlation import correlation_scope,source_operation,current_correlation
from external_data_client import ExternalDataClient

def test_provider_payload_does_not_inherit_core_cache(monkeypatch):
    import test_free_news_evidence_capacity as base
    monkeypatch.setattr(base,'DATA',{**deepcopy(base.DATA),'_cache_hit':True})
    result=base.fetch(monkeypatch,base.rows())
    assert result.audit['cache_hit']is False
    assert result.audit['record_count']==8 and len(result.value)==8

def test_real_callback_children_keep_current_operation_without_claiming_http():
    client=ExternalDataClient(google_news=lambda *a,**k:[{'title':'same title','link':'https://example.test/news'}])
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      with source_operation('recent_catalysts','Free news waterfall'):
        expected=current_correlation()
        result=client.get_news('private query',limit=1)
    assert len(result)==len(client.last_news_audit)==1
    child=client.last_news_audit[0]
    assert child['operation_id']==expected['operation_id']and child['fetch_id']=='fetch'
    assert 'http_request_sent'not in child and 'private query'not in str(child)

def test_error_child_does_not_lose_operation_or_invent_delivery():
    def failed(*a,**k):raise ValueError('failure')
    client=ExternalDataClient(google_news=failed)
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      with source_operation('recent_catalysts','Free news waterfall'):
        expected=current_correlation();assert client._safe_news('Google News RSS',failed,'private',1)==[]
    child=client.last_news_audit[0]
    assert child['status']=='error'and child['error_kind']=='ValueError'
    assert child['operation_id']==expected['operation_id']
    assert 'http_request_sent'not in child


def test_foreign_source_cannot_lend_its_operation():
    client=ExternalDataClient(google_news=lambda *a,**k:[{'title':'title','link':'https://example.test/news'}])
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='foreign-fetch'):
      with source_operation('macro_indicators','other'):
        client.get_news('private',limit=1)
    assert 'operation_id'not in client.last_news_audit[0]
    assert 'fetch_id'not in client.last_news_audit[0]

def test_sibling_callbacks_keep_distinct_operations_and_parent_context():
    client=ExternalDataClient(google_news=lambda *a,**k:[{'title':'title','link':'https://example.test/news'}])
    operations=[]
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      before=current_correlation()
      for _ in range(2):
        with source_operation('recent_catalysts','Free news waterfall'):
          client.get_news('private',limit=1)
          operations.append(client.last_news_audit[0]['operation_id'])
      assert current_correlation()==before
    assert operations[0]!=operations[1]
