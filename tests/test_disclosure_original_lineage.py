import json,httpx
from provider_correlation import correlation_scope,source_operation
from official_response_evidence import read_response
from test_official_disclosure_sources import row,NOW
import official_disclosure_sources as m

def test_native_daily_snapshot_keeps_original_and_identical_parser_output(monkeypatch):
    body=json.dumps([row()],ensure_ascii=False).encode()
    response=httpx.Response(200,content=body,request=httpx.Request('GET',m.MARKETS['twse']['url']))
    calls=[];events=[]
    def get(*a,**k):calls.append(1);return response
    monkeypatch.setattr(m,'sync_get',get)
    monkeypatch.setattr(m,'cooldown_state',lambda key:{})
    monkeypatch.setattr(m.time,'time',lambda:NOW)
    monkeypatch.setattr(m,'record_observation',lambda *a,**k:events.append(k))
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      with source_operation('official_disclosures','TWSE/TPEx official disclosures'):
        result=m._fetch_snapshot('twse','guard')
    assert len(calls)==len(events)==1
    receipt=result['diagnostic']['raw_http_receipt']
    assert receipt['status']=='archived'and read_response(receipt,max_bytes=10*1024*1024)==body
    replay,rejected=m.parse_disclosure_rows(json.loads(read_response(receipt)), 'twse',observed_at_epoch=result['retrieved_at_epoch'])
    assert replay==result['documents']and rejected==0
    assert events[0]['count']==1 and result['diagnostic']['coverage_status']=='partial'


import pytest
@pytest.fixture
def setup_snapshot(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    body=json.dumps([row()],ensure_ascii=False).encode()
    response=httpx.Response(200,content=body,request=httpx.Request('GET',m.MARKETS['twse']['url']))
    calls=[]
    def get(*a,**k):calls.append(1);return response
    monkeypatch.setattr(m,'sync_get',get)
    monkeypatch.setattr(m,'cooldown_state',lambda key:{})
    monkeypatch.setattr(m.time,'time',lambda:NOW)
    yield response,calls,body
    cache_store.reset_cache_store_for_tests()

def invoke():
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      with source_operation('official_disclosures','TWSE/TPEx official disclosures'):
        return m._fetch_snapshot('twse','guard')

@pytest.mark.parametrize('change',['cache','url','auth','cookie','wrong_owner','unknown_client'])
def test_ambiguous_delivery_cannot_create_original(monkeypatch,setup_snapshot,change):
    from types import SimpleNamespace
    response,calls,body=setup_snapshot
    if change=='cache':response.from_cache=True
    if change=='url':response.request=httpx.Request('GET','https://other.example/data')
    if change in {'auth','cookie'}:response.request.headers['Authorization'if change=='auth'else 'Cookie']='PRIVATE'
    if change=='unknown_client':
        fake=SimpleNamespace(content=body,status_code=200,url=response.url,request=response.request,json=response.json,raise_for_status=lambda:None)
        monkeypatch.setattr(m,'sync_get',lambda *a,**k:fake)
    if change=='wrong_owner':
        with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
          with source_operation('macro_indicators','other'):result=m._fetch_snapshot('twse','guard')
    else:result=invoke()
    assert len(result['documents'])==1
    assert 'raw_http_receipt'not in result['diagnostic']

@pytest.mark.parametrize('mode',['exception','unavailable'])
def test_archive_failure_keeps_acquired_content(monkeypatch,setup_snapshot,mode):
    import official_response_evidence as archive
    response,calls,body=setup_snapshot
    def fail(*a,**k):
        if mode=='exception':raise OSError('archive unavailable')
        return {'status':'unavailable'}
    monkeypatch.setattr(archive,'archive_response',fail)
    result=invoke()
    assert len(calls)==len(result['documents'])==1
    assert result['documents'][0]['text']==row()['說明']
    assert 'raw_http_receipt'not in result['diagnostic']

@pytest.mark.parametrize('status',[403,429,503,504])
def test_error_response_is_not_archived_or_retried(monkeypatch,setup_snapshot,status):
    import official_response_evidence as archive
    response,calls,body=setup_snapshot
    response.status_code=status
    archived=[];monkeypatch.setattr(archive,'archive_response',lambda *a,**k:archived.append(1))
    with pytest.raises(m.SourceResponseError):invoke()
    assert len(calls)==1 and not archived

def test_normal_shared_cache_preserves_original_timestamp_without_new_send(monkeypatch,setup_snapshot):
    from provider_acquisition import observation_kind
    response,calls,body=setup_snapshot
    with correlation_scope(replace=True,ticker='2330.TW',fetch_id='fetch'):
      with source_operation('official_disclosures','TWSE/TPEx official disclosures'):
        first,initial=m.fetch_disclosure_snapshot('twse')
        monkeypatch.setattr(m.time,'time',lambda:NOW+20)
        warm,audit=m.fetch_disclosure_snapshot('twse')
    assert len(calls)==1 and warm['documents']==first['documents']
    assert audit['cache_hit']is True and audit['http_request_sent']is False
    assert audit['fetched_at_epoch']==initial['fetched_at_epoch']==NOW
    assert audit['raw_http_receipt']==initial['raw_http_receipt']
    assert m.FRESHNESS_SECONDS==300
    assert observation_kind({'source':m.SOURCE,'provider':m.MARKETS['twse']['provider'],'status':'success','record_count':1,'message':'','details':audit})=='fresh_cache_count'

def test_existing_single_observation_persists_original_proof(monkeypatch,setup_snapshot,tmp_path):
    import provider_sla,sqlite3
    response,calls,body=setup_snapshot
    monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'audit.sqlite3'))
    result=invoke()
    with sqlite3.connect(tmp_path/'audit.sqlite3')as db:
        db.row_factory=sqlite3.Row
        rows=[dict(r)for r in db.execute('select * from provider_sla_events')]
    assert len(rows)==1 and rows[0]['record_count']==1
    d=json.loads(rows[0]['details_json']);proof=d['original_http_receipts'][0]
    assert proof['response_sha256']==result['diagnostic']['response_sha256']
    assert proof['http_status_observed']is True and proof['response_complete']is True
    assert proof['original_cache_hit']is False and d['coverage_status']=='partial'
    assert row()['說明']not in rows[0]['details_json']
